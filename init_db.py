import argparse
import json
from pathlib import Path

from db import BASE_DIR, connect


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


TABLES_IN_DROP_ORDER = (
    "resource_suggestion",
    "maintenance_issue",
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
                    ensure_inventory_columns(cursor)
                    ensure_request_workflow(cursor)
                    ensure_collection_locations(cursor)
                    ensure_circulation_tracking(cursor)
                connection.commit()
                print(f"{filename}: executed {count} SQL statements")
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