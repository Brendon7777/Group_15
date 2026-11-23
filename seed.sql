INSERT INTO `users`
  (`user_id`, `full_name`, `school_id`, `email`, `password_hash`, `role`, `grade`)
VALUES
  (1, 'Ayesha Jacobs', 'T-1005', 'g2.teacher1@example.com',
   'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa',
   'staff', 'Grade 2'),
  (2, 'Lwazi Mthembu', 'L-3001', 'learner01@example.com',
   'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa',
   'learner', NULL),
  (3, 'Nomsa Khumalo', 'C-2001', 'ltsm01@example.com',
   'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa',
   'ltsm', NULL),
  (4, 'Thandi Nkosi', 'T-1001', 'g1.teacher1@example.com',
   'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa',
   'staff', 'Grade 1'),
  (5, 'Naledi Molefe', 'T-1003', 'g3.teacher1@example.com',
   'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa',
   'staff', 'Grade 3'),
  (6, 'Amogelang Mokoena', 'L-3002', 'learner02@example.com',
   'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa',
   'learner', 'Grade 2');

INSERT INTO `resource`
  (`resource_id`, `resource_name`, `category`, `grade`, `quantity_owned`,
   `quantity_in_stock`, `reorder_level`, `description`, `unit_of_measure`,
   `unit_price`, `review_policy`)
VALUES
  (1, 'Grade 8 Natural Sciences textbook', 'Textbooks', 'Grade 8', 25, 18, 10,
   'Student textbook, 3rd edition', 'copies', 320.00, 'annual'),
  (2, 'Mathematics textbook', 'Textbooks', 'Grade 7', 20, 4, 8,
   'Core learning textbook, 2nd edition', 'copies', 280.00, 'annual'),
  (3, 'A4 exercise books', 'Stationery', NULL, 60, 8, 15,
   '72-page ruled books', 'packs', 140.00, 'six_month'),
  (4, 'Whiteboard markers', 'Stationery', NULL, 40, 12, 10,
   'Assorted colours', 'packs', 64.50, 'six_month'),
  (5, 'Classroom projector', 'Equipment', NULL, 3, 2, 1,
   'HD projector with HDMI connection', 'units', 8500.00, NULL),
  (6, 'Tablet set', 'Equipment', NULL, 2, 1, 1,
   'Shared set of ten tablet devices', 'sets', 25000.00, NULL),
  (7, 'Portable speaker', 'Equipment', NULL, 5, 3, 1,
   'Bluetooth classroom speaker', 'units', 1200.00, NULL),
  (8, 'Document camera', 'Equipment', NULL, 2, 1, 1,
   'USB camera for live demonstrations', 'units', 4500.00, NULL),
  (9, 'Geometry set', 'Stationery', 'Grade 8', 30, 20, 10,
   'Compass, protractor and rulers', 'sets', 95.00, 'six_month'),
  (10, 'Grade 3 DBE Mathematics workbook', 'Textbooks', 'Grade 3', 25, 25, 5,
   'DBE workbook, Mathematics', 'books', 80.00, 'annual'),
  (11, 'Grade 2 DBE English workbook', 'Textbooks', 'Grade 2', 25, 19, 5,
   'DBE workbook, English', 'books', 80.00, 'annual'),
  (12, 'Learner stationery pack', 'Stationery', 'Grade 1', 30, 16, 8,
   'Pens, pencils and basic stationery', 'packs', 140.00, 'six_month'),
  (13, 'Printer ink cartridge', 'Stationery', NULL, 12, 6, 4,
   'Replacement ink cartridge', 'cartridges', 350.00, 'six_month'),
  (14, 'Abacus', 'Other', 'Grade 1', 200, 200, 20,
   'Reusable classroom counting aid', 'units', 220.00, NULL),
  (15, 'Teaching clock', 'Other', 'Grade 2', 8, 4, 2,
   'Reusable classroom teaching clock', 'units', 180.00, NULL),
  (16, 'Laptop type A', 'Equipment', NULL, 5, 5, 1,
   'Reusable school laptop', 'units', 8000.00, NULL),
  (17, 'Printer A', 'Equipment', NULL, 1, 1, 1,
   'Reusable school printer', 'units', 6500.00, NULL);

INSERT INTO `consumable_demand_history`
  (`resource_id`, `history_start`, `history_end`, `demand_values`)
VALUES
  (3, '2025-01-01', '2025-06-30', '[40, 45, 38, 42, 50, 48]'),
  (4, '2025-01-01', '2025-06-30', '[12, 14, 10, 16, 18, 15]'),
  (9, '2025-01-01', '2025-06-30', '[8, 10, 7, 9, 12, 11]'),
  (12, '2025-01-01', '2025-06-30', '[20, 22, 18, 25, 24, 21]'),
  (13, '2025-01-01', '2025-06-30', '[3, 4, 3, 5, 4, 5]'),
  (10, '2023-01-01', '2025-12-31', '[140, 148, 136]'),
  (11, '2023-01-01', '2025-12-31', '[156, 162, 150]');

INSERT INTO `resource_request`
  (`request_id`, `user_id`, `resource_name`, `category`, `quantity`,
   `needed_by`, `purpose`, `submitted_date`, `status`, `latest_update`)
VALUES
  (1, 1, 'Grade 8 science workbook', 'Textbooks', 30,
   DATE_ADD(CURDATE(), INTERVAL 4 DAY),
   'For the Grade 8 Natural Sciences practical programme.',
   DATE_SUB(CURDATE(), INTERVAL 10 DAY), 'In review', 'Committee review in progress'),
  (2, 1, 'Whiteboard markers', 'Stationery', 2,
   DATE_ADD(CURDATE(), INTERVAL 14 DAY),
   'Replacement markers for the mathematics classroom.',
   DATE_SUB(CURDATE(), INTERVAL 14 DAY), 'Approved', 'Approved - collection details to follow'),
  (3, 1, 'Geometry sets', 'Stationery', 5,
   DATE_ADD(CURDATE(), INTERVAL 7 DAY),
   'Sets are needed for the upcoming geometry unit.',
   DATE_SUB(CURDATE(), INTERVAL 19 DAY), 'Ready for collection', 'Collect from the resource office'),
  (4, 1, 'Personal laptop', 'Equipment', 1,
   NULL, 'A personal device for lesson preparation.',
   DATE_SUB(CURDATE(), INTERVAL 24 DAY), 'Declined', 'Outside the school equipment catalogue'),
  (5, 2, 'Whiteboard markers - class pack', 'Stationery', 3,
   DATE_ADD(CURDATE(), INTERVAL 9 DAY),
   'Markers are needed for group research presentations.',
   DATE_SUB(CURDATE(), INTERVAL 2 DAY), 'In review', 'Committee review in progress'),
  (6, 2, 'Calculator set', 'Equipment', 1,
   DATE_ADD(CURDATE(), INTERVAL 2 DAY),
   'A shared calculator set is needed for the numeracy exercise.',
   DATE_SUB(CURDATE(), INTERVAL 3 DAY), 'In review', 'Committee review in progress');

INSERT INTO `equipment_booking`
  (`booking_id`, `user_id`, `resource_id`, `booking_date`, `start_time`,
   `end_time`, `room`, `purpose`, `status`)
VALUES
  (1, 1, 5, DATE_ADD(CURDATE(), INTERVAL 3 DAY),
   '10:00:00', '12:00:00', 'Room 12', 'Mathematics lesson', 'Confirmed'),
  (2, 2, 6, DATE_ADD(CURDATE(), INTERVAL 4 DAY),
   '09:00:00', '10:00:00', 'Library', 'Research task', 'Awaiting approval'),
  (3, 5, 7, DATE_ADD(CURDATE(), INTERVAL 6 DAY),
   '13:00:00', '14:30:00', 'Hall', 'Grade assembly', 'Confirmed');

INSERT INTO `item_movement`
  (`movement_id`, `resource_id`, `borrower_id`, `borrower_name`,
   `movement_type`, `quantity`, `movement_date`, `due_date`,
   `active_loan`, `recorded_by_user_id`)
VALUES
  (1, 1, 'L-2041', 'A. Mokoena', 'issue', 1,
   DATE_SUB(CURDATE(), INTERVAL 10 DAY), DATE_ADD(CURDATE(), INTERVAL 5 DAY),
   TRUE, 3),
  (2, 5, 'T-1005', 'Ayesha Jacobs', 'issue', 1,
   DATE_SUB(CURDATE(), INTERVAL 6 DAY), DATE_ADD(CURDATE(), INTERVAL 2 DAY),
   TRUE, 3),
  (3, 9, 'L-2087', 'T. Dlamini', 'issue', 1,
   DATE_SUB(CURDATE(), INTERVAL 17 DAY), DATE_SUB(CURDATE(), INTERVAL 3 DAY),
   TRUE, 3),
  (4, 1, 'T-1005', 'Ayesha Jacobs', 'issue', 1,
   DATE_SUB(CURDATE(), INTERVAL 2 DAY), DATE_ADD(CURDATE(), INTERVAL 12 DAY),
   TRUE, 3),
  (5, 11, 'L-3002', 'Amogelang Mokoena', 'return', 1,
   DATE_SUB(CURDATE(), INTERVAL 1 DAY), NULL,
   FALSE, 3);

INSERT INTO `maintenance_issue`
  (`issue_id`, `resource_id`, `equipment_or_item`, `reported_by_user_id`,
   `reported_by_name`, `priority`, `reported_date`, `description`, `status`)
VALUES
  (1, 5, 'Projector - PRJ-014', 3, 'Nomsa Khumalo',
   'High', DATE_SUB(CURDATE(), INTERVAL 10 DAY),
   'HDMI connection intermittent', 'In repair'),
  (2, 6, 'Tablet - TAB-022', 3, 'Nomsa Khumalo',
   'Urgent', DATE_SUB(CURDATE(), INTERVAL 12 DAY),
   'Screen does not respond', 'Out of service'),
  (3, 7, 'Speaker - SPK-005', 3, 'Nomsa Khumalo',
   'Low', DATE_SUB(CURDATE(), INTERVAL 15 DAY),
   'Battery replacement required', 'Resolved'),
  (4, 8, 'Document camera - CAM-003', 3, 'Nomsa Khumalo',
   'Normal', DATE_SUB(CURDATE(), INTERVAL 2 DAY),
   'Focus control needs adjustment', 'Open');