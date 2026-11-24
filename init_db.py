import argparse
import json
from pathlib import Path

from db import BASE_DIR, connect, database_name


LEGACY_DEMO_PASSWORD_HASH = (
    "pbkdf2:sha256:150000$QjP6lQp6$"
    "367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa"
)
DEMO_PASSWORD_HASH = (
    "pbkdf2:sha256:150000$vKcgYPg1Z8fcIUZF$"
    "95ad51a4980ed781ccfdbdd8f7e6153a36b8370ab7df90230be8bab0dfc3c7d3"
)


def read_statements(filename):
    path = BASE_DIR / filename
    with open(path, "r", encoding="utf-8") as sql_file:
        lines = [
            line
            for line in sql_file.read().splitlines()
            if not line.strip().startswith("--")
        ]

    sql_text = "\n".join(lines)
    return [
        statement.strip()
        for statement in sql_text.split(";")
        if statement.strip()
    ]


def run_sql_file(cursor, filename):
    statements = read_statements(filename)
    for statement in statements:
        cursor.execute(statement)
    return len(statements)


def ensure_database_exists():
    name = database_name()
    connection = connect(include_database=False)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        connection.commit()
    finally:
        connection.close()


TABLES_IN_DROP_ORDER = (
    "resource_suggestion",
    "maintenance_issue",
    "evidence_baseline",
    "evidence_period_completion",
    "operational_measurement",
    "user_notification",
    # Drop the audit table before the movement and resource rows it references.
    "inventory_adjustment",
    "item_movement",
    "equipment_booking",
    "resource_request",
    "collection_location",
    "consumable_demand_history",
    "resource",
    "users",
    "staff",
)


def reset_tables(cursor):
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    try:
        for table in TABLES_IN_DROP_ORDER:
            cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
    finally:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def resources_are_empty(cursor):
    cursor.execute("SELECT COUNT(*) AS row_count FROM `resource`")
    return cursor.fetchone()["row_count"] == 0


def migrate_legacy_demo_password_hash(cursor):
    cursor.execute(
        """
        UPDATE `users`
        SET `password_hash` = %s
        WHERE `password_hash` = %s
        """,
        (DEMO_PASSWORD_HASH, LEGACY_DEMO_PASSWORD_HASH),
    )
    return cursor.rowcount


def ensure_demo_evidence_examples(cursor):
    cursor.execute(
        "SELECT user_id FROM `users` WHERE `role` = 'ltsm' ORDER BY user_id LIMIT 1"
    )
    committee = cursor.fetchone()
    recorded_by_user_id = committee["user_id"] if committee else None
    inserted = 0

    baseline_examples = (
        (
            "inventory_accuracy",
            "2025-09-01",
            "2025-09-30",
            92.00,
            25,
            "DEMO DATA ONLY: illustrative baseline - replace with measured observations.",
        ),
        (
            "report_preparation",
            "2025-09-01",
            "2025-09-30",
            24.00,
            4,
            "DEMO DATA ONLY: illustrative baseline - replace with measured observations.",
        ),
    )
    for metric_key, period_start, period_end, value, sample_count, notes in baseline_examples:
        cursor.execute(
            """
            INSERT IGNORE INTO `evidence_baseline`
              (`metric_key`, `period_start`, `period_end`, `measure_value`,
               `sample_count`, `notes`, `recorded_by_user_id`, `is_demo`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            """,
            (
                metric_key, period_start, period_end, value, sample_count,
                notes, recorded_by_user_id,
            ),
        )
        inserted += cursor.rowcount

    observation_examples = (
        ("inventory_count", None, 18, 18, "DEMO DATA: sample physical count matched the recorded quantity."),
        ("report_preparation", 24.00, None, None, "DEMO DATA: sample report preparation duration."),
    )
    for metric_key, duration, expected_quantity, actual_quantity, notes in observation_examples:
        cursor.execute(
            """
            SELECT `measurement_id` FROM `operational_measurement`
            WHERE `is_demo` = TRUE AND `metric_key` = %s AND `notes` = %s
            LIMIT 1
            """,
            (metric_key, notes),
        )
        if cursor.fetchone():
            continue
        cursor.execute(
            """
            INSERT INTO `operational_measurement`
              (`metric_key`, `occurred_at`, `duration_minutes`, `expected_quantity`,
               `actual_quantity`, `notes`, `recorded_by_user_id`, `is_demo`)
            VALUES (%s, DATE_SUB(CURRENT_TIMESTAMP(6), INTERVAL 60 DAY), %s, %s,
                    %s, %s, %s, TRUE)
            """,
            (
                metric_key, duration, expected_quantity, actual_quantity, notes,
                recorded_by_user_id,
            ),
        )
        inserted += cursor.rowcount

    return inserted


def ensure_user_active_column(cursor):
    cursor.execute(
        """
        SELECT COUNT(*) AS column_count
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'users'
          AND column_name = 'is_active'
        """
    )
    if cursor.fetchone()["column_count"] == 0:
        cursor.execute(
            "ALTER TABLE `users` ADD COLUMN `is_active` BOOLEAN NOT NULL DEFAULT TRUE"
        )


def ensure_user_account_status_column(cursor):
    cursor.execute(
        """
        SELECT COUNT(*) AS column_count
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'users'
          AND column_name = 'account_status'
        """
    )
    if cursor.fetchone()["column_count"] == 0:
        cursor.execute(
            "ALTER TABLE `users` ADD COLUMN `account_status` "
            "ENUM('pending', 'approved') NOT NULL DEFAULT 'approved'"
        )


def ensure_notification_done_column(cursor):
    cursor.execute(
        """
        SELECT COUNT(*) AS column_count
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'user_notification'
          AND column_name = 'done_at'
        """
    )
    if cursor.fetchone()["column_count"] == 0:
        cursor.execute(
            "ALTER TABLE `user_notification` ADD COLUMN `done_at` TIMESTAMP NULL DEFAULT NULL AFTER `read_at`"
        )


def ensure_demo_data_columns(cursor):
    for table in (
        "operational_measurement",
        "evidence_baseline",
        "evidence_period_completion",
    ):
        cursor.execute(
            """
            SELECT COUNT(*) AS column_count
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = %s
              AND column_name = 'is_demo'
            """,
            (table,),
        )
        if cursor.fetchone()["column_count"] == 0:
            cursor.execute(
                f"ALTER TABLE `{table}` "
                "ADD COLUMN `is_demo` BOOLEAN NOT NULL DEFAULT FALSE"
            )


def ensure_demand_history_source_column(cursor):
    cursor.execute(
        """
        SELECT COUNT(*) AS column_count
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'consumable_demand_history'
          AND column_name = 'history_source'
        """
    )
    if cursor.fetchone()["column_count"] == 0:
        cursor.execute(
            "ALTER TABLE `consumable_demand_history` "
            "ADD COLUMN `history_source` "
            "ENUM('recorded', 'illustrative', 'unverified') "
            "NOT NULL DEFAULT 'unverified' AFTER `demand_values`"
        )


def ensure_updated_at_columns(cursor):
    tables = {
        "users": "created_at",
        "resource": "created_at",
        "resource_request": "submitted_at",
        "equipment_booking": "created_at",
        "item_movement": "created_at",
        "maintenance_issue": "created_at",
        "collection_location": "created_at",
    }
    for table, source_column in tables.items():
        cursor.execute(
            """
            SELECT COUNT(*) AS column_count
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = %s
              AND column_name = 'updated_at'
            """,
            (table,),
        )
        if cursor.fetchone()["column_count"]:
            continue
        cursor.execute(
            f"ALTER TABLE `{table}` "
            "ADD COLUMN `updated_at` TIMESTAMP NULL DEFAULT NULL "
            "ON UPDATE CURRENT_TIMESTAMP"
        )
        cursor.execute(
            f"UPDATE `{table}` SET `updated_at` = `{source_column}` "
            "WHERE `updated_at` IS NULL"
        )
        cursor.execute(
            f"ALTER TABLE `{table}` MODIFY COLUMN `updated_at` "
            "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP "
            "ON UPDATE CURRENT_TIMESTAMP"
        )


def ensure_movement_borrower_user_fk(cursor):
    cursor.execute(
        """
        SELECT COUNT(*) AS column_count
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'item_movement'
          AND column_name = 'borrower_user_id'
        """
    )
    if cursor.fetchone()["column_count"] == 0:
        cursor.execute(
            "ALTER TABLE `item_movement` "
            "ADD COLUMN `borrower_user_id` INT DEFAULT NULL AFTER `resource_id`"
        )

    cursor.execute(
        """
        UPDATE `item_movement` AS movement
        JOIN `users` AS borrower
          ON LOWER(borrower.`school_id`) = LOWER(movement.`borrower_id`)
        SET movement.`borrower_user_id` = borrower.`user_id`
        WHERE movement.`borrower_user_id` IS NULL
        """
    )
    cursor.execute(
        """
        SELECT COUNT(*) AS index_count
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = 'item_movement'
          AND index_name = 'item_movement_borrower_user_idx'
        """
    )
    if cursor.fetchone()["index_count"] == 0:
        cursor.execute(
            "ALTER TABLE `item_movement` "
            "ADD KEY `item_movement_borrower_user_idx` (`borrower_user_id`)"
        )
    cursor.execute(
        """
        SELECT COUNT(*) AS constraint_count
        FROM information_schema.key_column_usage
        WHERE table_schema = DATABASE()
          AND table_name = 'item_movement'
          AND constraint_name = 'item_movement_borrower_user_fk'
        """
    )
    if cursor.fetchone()["constraint_count"] == 0:
        cursor.execute(
            """
            ALTER TABLE `item_movement`
            ADD CONSTRAINT `item_movement_borrower_user_fk`
              FOREIGN KEY (`borrower_user_id`) REFERENCES `users` (`user_id`)
              ON UPDATE CASCADE ON DELETE SET NULL
            """
        )


def ensure_inventory_columns(cursor):
    cursor.execute(
        """
        SELECT column_name AS column_name
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'resource'
        """
    )
    columns = {row["column_name"] for row in cursor.fetchall()}
    if "storage_location" not in columns:
        cursor.execute(
            "ALTER TABLE `resource` ADD COLUMN `storage_location` VARCHAR(120) DEFAULT NULL"
        )
    if "inventory_type" not in columns:
        cursor.execute(
            "ALTER TABLE `resource` ADD COLUMN `inventory_type` ENUM('consumable', 'non_consumable') DEFAULT NULL AFTER `category`"
        )
    cursor.execute(
        """
        UPDATE `resource`
        SET `inventory_type` = CASE
          WHEN `category` IN ('Consumables', 'Stationery') THEN 'consumable'
          WHEN `category` IN ('Textbooks', 'Equipment') THEN 'non_consumable'
          ELSE NULL
        END
        WHERE `inventory_type` IS NULL AND `category` <> 'Other'
        """
    )

    cursor.execute(
        """
        ALTER TABLE `resource`
        MODIFY COLUMN `category`
          ENUM('Textbooks', 'Stationery', 'Consumables', 'Equipment', 'Other') NOT NULL
        """
    )
    cursor.execute(
        """
        ALTER TABLE `resource_request`
        MODIFY COLUMN `category`
          ENUM('Textbooks', 'Stationery', 'Consumables', 'Equipment', 'Other') NOT NULL
        """
    )
    cursor.execute(
        """
        ALTER TABLE `inventory_adjustment`
        MODIFY COLUMN `adjustment_type`
          ENUM('manual', 'received', 'damaged', 'lost', 'obsolete', 'issue', 'return') NOT NULL
        """
    )


def ensure_request_workflow(cursor):
    cursor.execute(
        """
        SELECT column_name AS column_name
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'resource_request'
        """
    )
    columns = {row["column_name"] for row in cursor.fetchall()}
    if "resource_id" not in columns:
        cursor.execute(
            "ALTER TABLE `resource_request` ADD COLUMN `resource_id` INT DEFAULT NULL AFTER `user_id`"
        )
    if "allocated_quantity" not in columns:
        cursor.execute(
            "ALTER TABLE `resource_request` ADD COLUMN `allocated_quantity` INT DEFAULT NULL AFTER `quantity`"
        )
    if "collection_slot" not in columns:
        cursor.execute(
            "ALTER TABLE `resource_request` ADD COLUMN `collection_slot` DATETIME DEFAULT NULL AFTER `allocated_quantity`"
        )
    if "submitted_at" not in columns:
        cursor.execute(
            "ALTER TABLE `resource_request` ADD COLUMN `submitted_at` DATETIME(6) DEFAULT NULL AFTER `submitted_date`"
        )
        cursor.execute(
            "UPDATE `resource_request` SET `submitted_at` = CAST(`submitted_date` AS DATETIME) WHERE `submitted_at` IS NULL"
        )
        cursor.execute(
            "ALTER TABLE `resource_request` MODIFY COLUMN `submitted_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)"
        )
    if "ready_at" not in columns:
        cursor.execute(
            "ALTER TABLE `resource_request` ADD COLUMN `ready_at` DATETIME(6) DEFAULT NULL AFTER `submitted_at`"
        )
    if "fulfilled_at" not in columns:
        cursor.execute(
            "ALTER TABLE `resource_request` ADD COLUMN `fulfilled_at` DATETIME(6) DEFAULT NULL AFTER `ready_at`"
        )

    cursor.execute(
        """
        SELECT COUNT(*) AS index_count
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = 'resource_request'
          AND index_name = 'resource_request_fifo_idx'
        """
    )
    if cursor.fetchone()["index_count"] == 0:
        cursor.execute(
            """
            ALTER TABLE `resource_request`
            ADD KEY `resource_request_fifo_idx` (`resource_id`, `status`, `submitted_at`, `request_id`)
            """
        )

    cursor.execute(
        """
        ALTER TABLE `resource_request`
        MODIFY COLUMN `status`
          ENUM('In review', 'Approved', 'Ready for collection', 'Declined', 'Fulfilled')
          NOT NULL DEFAULT 'In review'
        """
    )
    cursor.execute(
        """
        SELECT COUNT(*) AS constraint_count
        FROM information_schema.key_column_usage
        WHERE table_schema = DATABASE()
          AND table_name = 'resource_request'
          AND constraint_name = 'resource_request_resource_fk'
        """
    )
    if cursor.fetchone()["constraint_count"] == 0:
        cursor.execute(
            """
            ALTER TABLE `resource_request`
            ADD KEY `resource_request_resource_idx` (`resource_id`),
            ADD CONSTRAINT `resource_request_resource_fk`
              FOREIGN KEY (`resource_id`) REFERENCES `resource` (`resource_id`)
              ON UPDATE CASCADE ON DELETE SET NULL
            """
        )
    cursor.execute(
        """
        UPDATE `resource_request` AS rr
        JOIN `resource` AS r
          ON LOWER(TRIM(r.`resource_name`)) = LOWER(TRIM(rr.`resource_name`))
        SET rr.`resource_id` = r.`resource_id`
        WHERE rr.`resource_id` IS NULL
        """
    )


def ensure_booking_evidence_timestamp(cursor):
    cursor.execute(
        """
        SELECT column_name AS column_name
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'equipment_booking'
        """
    )
    columns = {row["column_name"] for row in cursor.fetchall()}
    if "requested_at" not in columns:
        cursor.execute(
            "ALTER TABLE `equipment_booking` ADD COLUMN `requested_at` DATETIME(6) DEFAULT NULL AFTER `end_time`"
        )
    cursor.execute(
        "UPDATE `equipment_booking` SET `requested_at` = CAST(`created_at` AS DATETIME) WHERE `requested_at` IS NULL"
    )
    cursor.execute(
        "ALTER TABLE `equipment_booking` MODIFY COLUMN `requested_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)"
    )
    cursor.execute(
        """
        SELECT COUNT(*) AS index_count
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = 'equipment_booking'
          AND index_name = 'equipment_booking_requested_at_idx'
        """
    )
    if cursor.fetchone()["index_count"] == 0:
        cursor.execute(
            "ALTER TABLE `equipment_booking` ADD KEY `equipment_booking_requested_at_idx` (`requested_at`)"
        )


def ensure_operational_measurement_types(cursor):
    cursor.execute(
        """
        ALTER TABLE `operational_measurement`
        MODIFY COLUMN `metric_key`
          ENUM('unnecessary_trip', 'follow_up_enquiry', 'incorrect_fulfillment',
               'report_preparation', 'equipment_downtime', 'inventory_count',
               'booking_conflict', 'motion_time') NOT NULL
        """
    )
    cursor.execute(
        """
        ALTER TABLE `evidence_period_completion`
        MODIFY COLUMN `metric_key` VARCHAR(40) NOT NULL
        """
    )


def ensure_collection_locations(cursor):
    cursor.execute(
        """
        SELECT column_name AS column_name
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'resource_request'
        """
    )
    columns = {row["column_name"] for row in cursor.fetchall()}
    if "collection_location_id" not in columns:
        cursor.execute(
            """
            ALTER TABLE `resource_request`
            ADD COLUMN `collection_location_id` INT DEFAULT NULL AFTER `collection_slot`
            """
        )

    cursor.execute(
        """
        SELECT COUNT(*) AS constraint_count
        FROM information_schema.key_column_usage
        WHERE table_schema = DATABASE()
          AND table_name = 'resource_request'
          AND constraint_name = 'resource_request_collection_location_fk'
        """
    )
    if cursor.fetchone()["constraint_count"] == 0:
        cursor.execute(
            """
            ALTER TABLE `resource_request`
            ADD KEY `resource_request_collection_location_idx` (`collection_location_id`),
            ADD CONSTRAINT `resource_request_collection_location_fk`
              FOREIGN KEY (`collection_location_id`) REFERENCES `collection_location` (`location_id`)
              ON UPDATE CASCADE ON DELETE SET NULL
            """
        )

    cursor.executemany(
        """
        INSERT IGNORE INTO `collection_location` (`location_name`)
        VALUES (%s)
        """,
        (("Storage Room 01",), ("Printer Room 34",)),
    )


def ensure_circulation_tracking(cursor):
    cursor.execute(
        """
        SELECT column_name AS column_name
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'item_movement'
        """
    )
    columns = {row["column_name"] for row in cursor.fetchall()}
    if "issued_quantity" not in columns:
        cursor.execute(
            "ALTER TABLE `item_movement` ADD COLUMN `issued_quantity` INT DEFAULT NULL AFTER `quantity`"
        )
    if "related_issue_movement_id" not in columns:
        cursor.execute(
            "ALTER TABLE `item_movement` ADD COLUMN `related_issue_movement_id` INT DEFAULT NULL AFTER `due_date`"
        )
    if "reason" not in columns:
        cursor.execute(
            "ALTER TABLE `item_movement` ADD COLUMN `reason` VARCHAR(255) DEFAULT NULL AFTER `related_issue_movement_id`"
        )
    cursor.execute(
        """
        ALTER TABLE `item_movement`
        MODIFY COLUMN `movement_type` ENUM('issue', 'return', 'lost', 'damaged') NOT NULL
        """
    )
    cursor.execute(
        """
        UPDATE `item_movement`
        SET `issued_quantity` = `quantity`
        WHERE `movement_type` = 'issue' AND `issued_quantity` IS NULL
        """
    )
    cursor.execute(
        """
        SELECT COUNT(*) AS constraint_count
        FROM information_schema.key_column_usage
        WHERE table_schema = DATABASE()
          AND table_name = 'item_movement'
          AND constraint_name = 'item_movement_related_issue_fk'
        """
    )
    if cursor.fetchone()["constraint_count"] == 0:
        cursor.execute(
            """
            ALTER TABLE `item_movement`
            ADD KEY `item_movement_related_issue_idx` (`related_issue_movement_id`),
            ADD CONSTRAINT `item_movement_related_issue_fk`
              FOREIGN KEY (`related_issue_movement_id`) REFERENCES `item_movement` (`movement_id`)
              ON UPDATE CASCADE ON DELETE RESTRICT
            """
        )

    cursor.execute(
        """
        SELECT column_name AS column_name
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'inventory_adjustment'
        """
    )
    adjustment_columns = {row["column_name"] for row in cursor.fetchall()}
    if "quantity_owned_before" not in adjustment_columns:
        cursor.execute(
            "ALTER TABLE `inventory_adjustment` ADD COLUMN `quantity_owned_before` INT DEFAULT NULL AFTER `quantity_after`"
        )
    if "quantity_owned_after" not in adjustment_columns:
        cursor.execute(
            "ALTER TABLE `inventory_adjustment` ADD COLUMN `quantity_owned_after` INT DEFAULT NULL AFTER `quantity_owned_before`"
        )


def ensure_inventory_sample_history(cursor):
    cursor.execute(
        """
        SELECT COUNT(*) AS table_count
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
          AND table_name IN ('resource', 'consumable_demand_history')
        """
    )
    if cursor.fetchone()["table_count"] != 2:
        return 0

    six_month_samples = (
        (3, "A4 exercise books", [40, 45, 38, 42, 50, 48]),
        (4, "Whiteboard markers", [12, 14, 10, 16, 18, 15]),
        (9, "Geometry set", [8, 10, 7, 9, 12, 11]),
        (12, "Learner stationery pack", [20, 22, 18, 25, 24, 21]),
        (13, "Printer ink cartridge", [3, 4, 3, 5, 4, 5]),
    )
    updated = 0
    for resource_id, resource_name, expected_values in six_month_samples:
        cursor.execute(
            "SELECT `resource_name` FROM `resource` WHERE `resource_id` = %s",
            (resource_id,),
        )
        resource = cursor.fetchone()
        if resource is None or resource["resource_name"] != resource_name:
            continue

        cursor.execute(
            """
            SELECT `history_id`, `demand_values`
            FROM `consumable_demand_history`
            WHERE `resource_id` = %s
              AND `history_start` = '2025-01-01'
              AND `history_end` = '2025-12-31'
            """,
            (resource_id,),
        )
        for history in cursor.fetchall():
            raw_values = history["demand_values"]
            values = (
                json.loads(raw_values)
                if isinstance(raw_values, (str, bytes, bytearray))
                else raw_values
            )
            if values != expected_values:
                continue
            cursor.execute(
                """
                UPDATE `consumable_demand_history`
                SET `history_end` = '2025-06-30'
                WHERE `history_id` = %s
                """,
                (history["history_id"],),
            )
            updated += cursor.rowcount
            if resource_id in (9, 12):
                cursor.execute(
                    "UPDATE `resource` SET `review_policy` = 'six_month' WHERE `resource_id` = %s",
                    (resource_id,),
                )

    annual_samples = (
        (10, "Grade 3 DBE Mathematics workbook", [140, 148, 136]),
        (11, "Grade 2 DBE English workbook", [156, 162, 150]),
    )
    for resource_id, resource_name, annual_values in annual_samples:
        cursor.execute(
            """
            SELECT `resource_name`, `review_policy`
            FROM `resource`
            WHERE `resource_id` = %s
            """,
            (resource_id,),
        )
        resource = cursor.fetchone()
        if (
            resource is None
            or resource["resource_name"] != resource_name
            or resource["review_policy"] != "annual"
        ):
            continue
        cursor.execute(
            """
            SELECT COUNT(*) AS row_count
            FROM `consumable_demand_history`
            WHERE `resource_id` = %s
            """,
            (resource_id,),
        )
        if cursor.fetchone()["row_count"] == 0:
            cursor.execute(
                """
                INSERT INTO `consumable_demand_history`
                  (`resource_id`, `history_start`, `history_end`, `demand_values`)
                VALUES (%s, '2023-01-01', '2025-12-31', %s)
                """,
                (resource_id, json.dumps(annual_values)),
            )
            updated += cursor.rowcount
    return updated


def ensure_inventory_adjustment_history(cursor):
    cursor.execute(
        """
        SELECT COUNT(*) AS table_count
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
          AND table_name IN ('item_movement', 'inventory_adjustment')
        """
    )
    if cursor.fetchone()["table_count"] != 2:
        return 0

    cursor.execute(
        """
        INSERT IGNORE INTO `inventory_adjustment`
          (`resource_id`, `movement_id`, `adjustment_type`, `quantity_change`,
           `reason`, `recorded_by_user_id`, `created_at`)
        SELECT `resource_id`, `movement_id`, `movement_type`,
               CASE WHEN `movement_type` IN ('issue', 'lost', 'damaged')
                    THEN -`quantity` ELSE `quantity` END,
               CASE
                 WHEN `movement_type` = 'issue'
                   THEN CONCAT('Issued to ', `borrower_name`, ' (', `borrower_id`, ')')
                 WHEN `movement_type` = 'return'
                   THEN CONCAT('Returned by ', `borrower_name`, ' (', `borrower_id`, ')')
                 ELSE CONCAT('Marked ', `movement_type`, ' for ', `borrower_name`,
                             ' (', `borrower_id`, '): ', COALESCE(`reason`, ''))
               END,
               `recorded_by_user_id`, `created_at`
        FROM `item_movement`
        """
    )
    return cursor.rowcount


def main():
    parser = argparse.ArgumentParser(description="Initialize the LTSM MySQL database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing project tables before recreating the schema.",
    )
    parser.add_argument("sql_files", nargs="*", help="SQL files to run (default: schema.sql seed.sql).")
    args = parser.parse_args()
    sql_files = args.sql_files or ["schema.sql", "seed.sql"]

    ensure_database_exists()
    connection = connect()
    try:
        with connection.cursor() as cursor:
            if args.reset:
                reset_tables(cursor)
                connection.commit()

            for filename in sql_files:
                if Path(filename).name == "seed.sql" and not resources_are_empty(cursor):
                    print(f"{filename}: skipped because the resource table is not empty")
                    continue
                count = run_sql_file(cursor, filename)
                if Path(filename).name == "schema.sql":
                    ensure_user_active_column(cursor)
                    ensure_user_account_status_column(cursor)
                    ensure_notification_done_column(cursor)
                    ensure_demo_data_columns(cursor)
                    ensure_demand_history_source_column(cursor)
                    ensure_inventory_columns(cursor)
                    ensure_request_workflow(cursor)
                    ensure_updated_at_columns(cursor)
                    ensure_booking_evidence_timestamp(cursor)
                    ensure_operational_measurement_types(cursor)
                    ensure_collection_locations(cursor)
                    ensure_circulation_tracking(cursor)
                    ensure_movement_borrower_user_fk(cursor)
                connection.commit()
                print(f"{filename}: executed {count} SQL statements")
            if any(Path(filename).name in ("schema.sql", "seed.sql") for filename in sql_files):
                migrated_demo_accounts = migrate_legacy_demo_password_hash(cursor)
                if migrated_demo_accounts:
                    connection.commit()
                    print(
                        f"Updated the password hash for {migrated_demo_accounts} "
                        "unchanged demo account(s)"
                    )
            if any(Path(filename).name == "seed.sql" for filename in sql_files):
                demo_evidence_count = ensure_demo_evidence_examples(cursor)
                if demo_evidence_count:
                    connection.commit()
                    print(
                        f"Added {demo_evidence_count} illustrative demo evidence row(s)"
                    )
            migrated_history = ensure_inventory_sample_history(cursor)
            migrated_adjustments = ensure_inventory_adjustment_history(cursor)
            if migrated_history or migrated_adjustments:
                connection.commit()
                if migrated_history:
                    print(f"Updated {migrated_history} legacy sample inventory history record(s)")
                if migrated_adjustments:
                    print(f"Added {migrated_adjustments} existing movement(s) to the inventory audit trail")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()