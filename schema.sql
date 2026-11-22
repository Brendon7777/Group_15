CREATE TABLE IF NOT EXISTS `users` (
  `user_id` INT NOT NULL AUTO_INCREMENT,
  `full_name` VARCHAR(100) NOT NULL,
  `school_id` VARCHAR(40) NOT NULL,
  `email` VARCHAR(100) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `role` ENUM('learner', 'staff', 'ltsm') NOT NULL,
  `grade` VARCHAR(20) DEFAULT NULL,
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `users_email_unique` (`email`),
  UNIQUE KEY `users_school_id_unique` (`school_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `resource` (
  `resource_id` INT NOT NULL AUTO_INCREMENT,
  `resource_name` VARCHAR(100) NOT NULL,
  `category` ENUM('Textbooks', 'Stationery', 'Equipment', 'Other') NOT NULL,
  `grade` VARCHAR(20) DEFAULT NULL,
  `quantity_owned` INT NOT NULL DEFAULT 0,
  `quantity_in_stock` INT NOT NULL DEFAULT 0,
  `reorder_level` INT NOT NULL DEFAULT 0,
  `description` VARCHAR(255) DEFAULT NULL,
  `unit_of_measure` VARCHAR(45) NOT NULL,
  `unit_price` DECIMAL(10,2) DEFAULT NULL,
  `review_policy` ENUM('six_month', 'annual') DEFAULT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`resource_id`),
  UNIQUE KEY `resource_name_unique` (`resource_name`, `grade`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `consumable_demand_history` (
  `history_id` INT NOT NULL AUTO_INCREMENT,
  `resource_id` INT NOT NULL,
  `history_start` DATE NOT NULL,
  `history_end` DATE NOT NULL,
  `demand_values` JSON NOT NULL,
  PRIMARY KEY (`history_id`),
  KEY `consumable_demand_resource_idx` (`resource_id`),
  CONSTRAINT `consumable_demand_resource_fk`
    FOREIGN KEY (`resource_id`) REFERENCES `resource` (`resource_id`)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `resource_request` (
  `request_id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `resource_name` VARCHAR(100) NOT NULL,
  `category` ENUM('Textbooks', 'Stationery', 'Equipment', 'Other') NOT NULL,
  `quantity` INT NOT NULL,
  `needed_by` DATE DEFAULT NULL,
  `purpose` VARCHAR(500) NOT NULL,
  `submitted_date` DATE NOT NULL,
  `status` ENUM('In review', 'Approved', 'Ready for collection', 'Declined') NOT NULL DEFAULT 'In review',
  `latest_update` VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`request_id`),
  KEY `resource_request_user_idx` (`user_id`),
  KEY `resource_request_status_idx` (`status`),
  CONSTRAINT `resource_request_user_fk`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON UPDATE CASCADE
    ON DELETE RESTRICT,
  CONSTRAINT `resource_request_quantity_check` CHECK (`quantity` BETWEEN 1 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `equipment_booking` (
  `booking_id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `resource_id` INT NOT NULL,
  `booking_date` DATE NOT NULL,
  `start_time` TIME NOT NULL,
  `end_time` TIME NOT NULL,
  `room` VARCHAR(80) NOT NULL,
  `purpose` VARCHAR(160) NOT NULL,
  `status` ENUM('Awaiting approval', 'Confirmed', 'Declined') NOT NULL DEFAULT 'Awaiting approval',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`booking_id`),
  KEY `equipment_booking_user_idx` (`user_id`),
  KEY `equipment_booking_resource_idx` (`resource_id`),
  KEY `equipment_booking_slot_idx` (`resource_id`, `booking_date`, `start_time`, `end_time`),
  CONSTRAINT `equipment_booking_user_fk`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON UPDATE CASCADE
    ON DELETE RESTRICT,
  CONSTRAINT `equipment_booking_resource_fk`
    FOREIGN KEY (`resource_id`) REFERENCES `resource` (`resource_id`)
    ON UPDATE CASCADE
    ON DELETE RESTRICT,
  CONSTRAINT `equipment_booking_time_check` CHECK (`end_time` > `start_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `item_movement` (
  `movement_id` INT NOT NULL AUTO_INCREMENT,
  `resource_id` INT NOT NULL,
  `borrower_id` VARCHAR(40) NOT NULL,
  `borrower_name` VARCHAR(100) NOT NULL,
  `movement_type` ENUM('issue', 'return') NOT NULL,
  `quantity` INT NOT NULL,
  `movement_date` DATE NOT NULL,
  `due_date` DATE DEFAULT NULL,
  `active_loan` BOOLEAN NOT NULL DEFAULT FALSE,
  `recorded_by_user_id` INT DEFAULT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`movement_id`),
  KEY `item_movement_resource_idx` (`resource_id`),
  KEY `item_movement_borrower_idx` (`borrower_id`),
  KEY `item_movement_type_idx` (`movement_type`, `active_loan`),
  CONSTRAINT `item_movement_resource_fk`
    FOREIGN KEY (`resource_id`) REFERENCES `resource` (`resource_id`)
    ON UPDATE CASCADE
    ON DELETE RESTRICT,
  CONSTRAINT `item_movement_recorded_by_fk`
    FOREIGN KEY (`recorded_by_user_id`) REFERENCES `users` (`user_id`)
    ON UPDATE CASCADE
    ON DELETE SET NULL,
  CONSTRAINT `item_movement_quantity_check` CHECK (`quantity` BETWEEN 1 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `maintenance_issue` (
  `issue_id` INT NOT NULL AUTO_INCREMENT,
  `resource_id` INT DEFAULT NULL,
  `equipment_or_item` VARCHAR(100) NOT NULL,
  `reported_by_user_id` INT DEFAULT NULL,
  `reported_by_name` VARCHAR(80) NOT NULL,
  `priority` ENUM('Low', 'Normal', 'High', 'Urgent') NOT NULL,
  `reported_date` DATE NOT NULL,
  `description` VARCHAR(500) NOT NULL,
  `status` ENUM('Open', 'In repair', 'Out of service', 'Resolved') NOT NULL DEFAULT 'Open',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`issue_id`),
  KEY `maintenance_resource_idx` (`resource_id`),
  KEY `maintenance_status_idx` (`status`),
  CONSTRAINT `maintenance_resource_fk`
    FOREIGN KEY (`resource_id`) REFERENCES `resource` (`resource_id`)
    ON UPDATE CASCADE
    ON DELETE SET NULL,
  CONSTRAINT `maintenance_reported_by_fk`
    FOREIGN KEY (`reported_by_user_id`) REFERENCES `users` (`user_id`)
    ON UPDATE CASCADE
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;