INSERT INTO `users`
  (`user_id`, `full_name`, `school_id`, `email`, `password_hash`, `role`, `grade`)
VALUES
  (1, 'Ayesha Jacobs', 'T-1005', 'g2.teacher1@example.com',
   'pbkdf2:sha256:150000$vKcgYPg1Z8fcIUZF$95ad51a4980ed781ccfdbdd8f7e6153a36b8370ab7df90230be8bab0dfc3c7d3',
   'staff', 'Grade 2'),
  (2, 'Lwazi Mthembu', 'L-3001', 'learner01@example.com',
   'pbkdf2:sha256:150000$vKcgYPg1Z8fcIUZF$95ad51a4980ed781ccfdbdd8f7e6153a36b8370ab7df90230be8bab0dfc3c7d3',
   'learner', NULL),
  (3, 'Nomsa Khumalo', 'C-2001', 'ltsm01@example.com',
   'pbkdf2:sha256:150000$vKcgYPg1Z8fcIUZF$95ad51a4980ed781ccfdbdd8f7e6153a36b8370ab7df90230be8bab0dfc3c7d3',
   'ltsm', NULL),
  (4, 'Thandi Nkosi', 'T-1001', 'g1.teacher1@example.com',
   'pbkdf2:sha256:150000$vKcgYPg1Z8fcIUZF$95ad51a4980ed781ccfdbdd8f7e6153a36b8370ab7df90230be8bab0dfc3c7d3',
   'staff', 'Grade 1'),
  (5, 'Naledi Molefe', 'T-1003', 'g3.teacher1@example.com',
   'pbkdf2:sha256:150000$vKcgYPg1Z8fcIUZF$95ad51a4980ed781ccfdbdd8f7e6153a36b8370ab7df90230be8bab0dfc3c7d3',
   'staff', 'Grade 3'),
  (6, 'Amogelang Mokoena', 'L-3002', 'learner02@example.com',
   'pbkdf2:sha256:150000$vKcgYPg1Z8fcIUZF$95ad51a4980ed781ccfdbdd8f7e6153a36b8370ab7df90230be8bab0dfc3c7d3',
   'learner', 'Grade 2');

INSERT INTO `resource`
  (`resource_id`, `resource_name`, `category`, `inventory_type`, `grade`, `quantity_owned`,
   `quantity_in_stock`, `reorder_level`, `description`, `unit_of_measure`,
   `unit_price`, `review_policy`)
VALUES
  (1, 'Grade 1 Life Skills workbook', 'Textbooks', 'non_consumable', 'Grade 1', 25, 18, 10,
   'Foundation Phase Life Skills workbook', 'copies', 320.00, 'annual'),
  (2, 'Grade 1 Mathematics textbook', 'Textbooks', 'non_consumable', 'Grade 1', 20, 4, 8,
   'Foundation Phase Mathematics textbook', 'copies', 280.00, 'annual'),
  (3, 'A4 exercise books', 'Stationery', 'consumable', NULL, 60, 8, 15,
   '72-page ruled books', 'packs', 140.00, 'six_month'),
  (4, 'Whiteboard markers', 'Stationery', 'consumable', NULL, 40, 12, 10,
   'Assorted colours', 'packs', 64.50, 'six_month'),
  (5, 'Classroom projector', 'Equipment', 'non_consumable', NULL, 3, 2, 1,
   'HD projector with HDMI connection', 'units', 8500.00, NULL),
  (6, 'Tablet set', 'Equipment', 'non_consumable', NULL, 2, 1, 1,
   'Shared set of ten tablet devices', 'sets', 25000.00, NULL),
  (7, 'Portable speaker', 'Equipment', 'non_consumable', NULL, 5, 3, 1,
   'Bluetooth classroom speaker', 'units', 1200.00, NULL),
  (8, 'Document camera', 'Equipment', 'non_consumable', NULL, 2, 1, 1,
   'USB camera for live demonstrations', 'units', 4500.00, NULL),
  (9, 'Geometry set', 'Stationery', 'consumable', 'Grade 8', 30, 20, 10,
   'Compass, protractor and rulers', 'sets', 95.00, 'six_month'),
  (10, 'Grade 3 DBE Mathematics workbook', 'Textbooks', 'non_consumable', 'Grade 3', 25, 25, 5,
   'DBE workbook, Mathematics', 'books', 80.00, 'annual'),
  (11, 'Grade 2 DBE English workbook', 'Textbooks', 'non_consumable', 'Grade 2', 25, 19, 5,
   'DBE workbook, English', 'books', 80.00, 'annual'),
  (12, 'Learner stationery pack', 'Stationery', 'consumable', 'Grade 1', 30, 16, 8,
   'Pens, pencils and basic stationery', 'packs', 140.00, 'six_month'),
  (13, 'Printer ink cartridge', 'Stationery', 'consumable', NULL, 12, 6, 4,
   'Replacement ink cartridge', 'cartridges', 350.00, 'six_month'),
  (14, 'Abacus', 'Other', NULL, 'Grade 1', 200, 200, 20,
   'Reusable classroom counting aid', 'units', 220.00, NULL),
  (15, 'Teaching clock', 'Other', NULL, 'Grade 2', 8, 4, 2,
   'Reusable classroom teaching clock', 'units', 180.00, NULL),
  (16, 'Laptop type A', 'Equipment', 'non_consumable', NULL, 5, 5, 1,
   'Reusable school laptop', 'units', 8000.00, NULL),
  (17, 'Printer A', 'Equipment', 'non_consumable', NULL, 1, 1, 1,
   'Reusable school printer', 'units', 6500.00, NULL);

INSERT INTO `consumable_demand_history`
  (`resource_id`, `history_start`, `history_end`, `demand_values`, `history_source`)
VALUES
  (1, '2023-01-01', '2025-12-31', '[140, 148, 136]', 'illustrative'),
  (2, '2023-01-01', '2025-12-31', '[156, 162, 150]', 'illustrative'),
  (3, '2025-01-01', '2025-06-30', '[40, 45, 38, 42, 50, 48]', 'illustrative'),
  (4, '2025-01-01', '2025-06-30', '[12, 14, 10, 16, 18, 15]', 'illustrative'),
  (9, '2025-01-01', '2025-06-30', '[8, 10, 7, 9, 12, 11]', 'illustrative'),
  (12, '2025-01-01', '2025-06-30', '[20, 22, 18, 25, 24, 21]', 'illustrative'),
  (13, '2025-01-01', '2025-06-30', '[3, 4, 3, 5, 4, 5]', 'illustrative'),
  (10, '2023-01-01', '2025-12-31', '[140, 148, 136]', 'illustrative'),
  (11, '2023-01-01', '2025-12-31', '[156, 162, 150]', 'illustrative');

INSERT IGNORE INTO `collection_location` (`location_name`)
VALUES
  ('Storage Room 01'),
  ('Printer Room 34');

INSERT INTO `resource_request`
  (`request_id`, `user_id`, `resource_name`, `category`, `quantity`,
   `needed_by`, `purpose`, `submitted_date`, `status`, `latest_update`)
VALUES
  (1, 1, 'Grade 1 Life Skills workbook', 'Textbooks', 30,
   DATE_ADD(CURDATE(), INTERVAL 4 DAY),
   'For the Grade 1 Life Skills programme.',
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

INSERT INTO `inventory_adjustment`
  (`resource_id`, `movement_id`, `adjustment_type`, `quantity_change`,
   `reason`, `recorded_by_user_id`)
VALUES
  (1, 1, 'issue', -1, 'DEMO DATA: issued to learner L-2041', 3),
  (5, 2, 'issue', -1, 'DEMO DATA: issued to staff member T-1005', 3),
  (9, 3, 'issue', -1, 'DEMO DATA: issued to learner L-2087', 3),
  (1, 4, 'issue', -1, 'DEMO DATA: issued to staff member T-1005', 3),
  (11, 5, 'return', 1, 'DEMO DATA: returned by learner L-3002', 3);

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

INSERT INTO `resource_suggestion`
  (`user_id`, `submitter_name`, `resource_name`, `message`)
VALUES
  (1, 'Ayesha Jacobs', 'Large-print story cards',
   'DEMO DATA: consider adding large-print story cards for shared reading.'),
  (NULL, 'Foundation Phase staff', 'Classroom number line',
   'DEMO DATA: a reusable number line would support Grade 1-3 numeracy.');

INSERT INTO `user_notification`
  (`user_id`, `module`, `title`, `message`, `target_url`, `read_at`, `done_at`)
VALUES
  (3, 'request-management', 'DEMO DATA: new resource request',
   'A sample request is awaiting committee review.', 'request-management.html',
   CURRENT_TIMESTAMP(6), CURRENT_TIMESTAMP(6)),
  (1, 'my-requests', 'DEMO DATA: request update',
   'A sample request has been approved.', 'my-requests.html',
   CURRENT_TIMESTAMP(6), CURRENT_TIMESTAMP(6));

INSERT INTO `operational_measurement`
  (`metric_key`, `occurred_at`, `ended_at`, `duration_minutes`, `resource_id`,
   `expected_quantity`, `actual_quantity`, `notes`, `recorded_by_user_id`, `is_demo`)
VALUES
  ('unnecessary_trip', DATE_SUB(CURRENT_TIMESTAMP(6), INTERVAL 60 DAY), NULL,
   NULL, NULL, NULL, NULL, 'DEMO DATA: avoidable trip caused by unavailable stock.', 3, TRUE),
  ('follow_up_enquiry', DATE_SUB(CURRENT_TIMESTAMP(6), INTERVAL 60 DAY), NULL,
   NULL, NULL, NULL, NULL, 'DEMO DATA: requester asked for a status update.', 3, TRUE),
  ('incorrect_fulfillment', DATE_SUB(CURRENT_TIMESTAMP(6), INTERVAL 60 DAY), NULL,
   NULL, NULL, NULL, NULL, 'DEMO DATA: sample item correction during fulfillment.', 3, TRUE),
  ('report_preparation', DATE_SUB(CURRENT_TIMESTAMP(6), INTERVAL 60 DAY), NULL,
   24.00, NULL, NULL, NULL, 'DEMO DATA: sample report preparation duration.', 3, TRUE),
  ('equipment_downtime', DATE_SUB(CURRENT_TIMESTAMP(6), INTERVAL 60 DAY),
   DATE_SUB(CURRENT_TIMESTAMP(6), INTERVAL 58 DAY), NULL, 6, NULL, NULL,
   'DEMO DATA: sample tablet outage, later returned to service.', 3, TRUE),
  ('inventory_count', DATE_SUB(CURRENT_TIMESTAMP(6), INTERVAL 60 DAY), NULL,
   NULL, 1, 18, 18, 'DEMO DATA: sample physical count matched the recorded quantity.', 3, TRUE),
  ('booking_conflict', DATE_SUB(CURRENT_TIMESTAMP(6), INTERVAL 60 DAY), NULL,
   NULL, 5, NULL, NULL, 'DEMO DATA: sample booking attempt blocked by a reservation.', 3, TRUE),
  ('motion_time', DATE_SUB(CURRENT_TIMESTAMP(6), INTERVAL 60 DAY), NULL,
   12.50, NULL, NULL, NULL, 'DEMO DATA: sample time spent searching for inventory.', 3, TRUE);

INSERT INTO `evidence_baseline`
  (`metric_key`, `period_start`, `period_end`, `measure_value`, `sample_count`,
   `notes`, `recorded_by_user_id`, `is_demo`)
VALUES
  ('request_waiting', '2025-09-01', '2025-09-30', 45.00, 12,
   'DEMO DATA ONLY: illustrative baseline - replace with measured observations.', 3, TRUE),
  ('collection_waiting', '2025-09-01', '2025-09-30', 18.00, 8,
   'DEMO DATA ONLY: illustrative baseline - replace with measured observations.', 3, TRUE),
  ('request_fulfillment', '2025-09-01', '2025-09-30', 63.00, 8,
   'DEMO DATA ONLY: illustrative baseline - replace with measured observations.', 3, TRUE),
  ('unnecessary_trips', '2025-09-01', '2025-09-30', 5.00, 12,
   'DEMO DATA ONLY: illustrative baseline - replace with measured observations.', 3, TRUE),
  ('follow_up_enquiries', '2025-09-01', '2025-09-30', 8.00, 12,
   'DEMO DATA ONLY: illustrative baseline - replace with measured observations.', 3, TRUE),
  ('inventory_accuracy', '2025-09-01', '2025-09-30', 92.00, 25,
   'DEMO DATA ONLY: illustrative baseline - replace with measured observations.', 3, TRUE),
  ('potential_excess_stock', '2025-09-01', '2025-09-30', 2500.00, 5,
   'DEMO DATA ONLY: illustrative baseline - replace with measured observations.', 3, TRUE),
  ('booking_conflicts', '2025-09-01', '2025-09-30', 10.00, 20,
   'DEMO DATA ONLY: illustrative baseline - replace with measured observations.', 3, TRUE),
  ('report_preparation', '2025-09-01', '2025-09-30', 24.00, 4,
   'DEMO DATA ONLY: illustrative baseline - replace with measured observations.', 3, TRUE),
  ('motion_time', '2025-09-01', '2025-09-30', 55.00, 8,
   'DEMO DATA ONLY: illustrative baseline - replace with measured observations.', 3, TRUE),
  ('incorrect_fulfillment', '2025-09-01', '2025-09-30', 2.00, 8,
   'DEMO DATA ONLY: illustrative baseline - replace with measured observations.', 3, TRUE),
  ('equipment_downtime', '2025-09-01', '2025-09-30', 4.00, 3,
   'DEMO DATA ONLY: illustrative baseline - replace with measured observations.', 3, TRUE);

INSERT INTO `evidence_period_completion`
  (`metric_key`, `period_start`, `period_end`, `completed_at`,
   `recorded_by_user_id`, `is_demo`)
VALUES
  ('unnecessary_trips', '2025-10-01', '2025-10-31', '2025-11-02 12:00:00', 3, TRUE),
  ('follow_up_enquiries', '2025-10-01', '2025-10-31', '2025-11-02 12:00:00', 3, TRUE),
  ('inventory_accuracy', '2025-10-01', '2025-10-31', '2025-11-02 12:00:00', 3, TRUE),
  ('report_preparation', '2025-10-01', '2025-10-31', '2025-11-02 12:00:00', 3, TRUE),
  ('motion_time', '2025-10-01', '2025-10-31', '2025-11-02 12:00:00', 3, TRUE),
  ('incorrect_fulfillment', '2025-10-01', '2025-10-31', '2025-11-02 12:00:00', 3, TRUE),
  ('equipment_downtime', '2025-10-01', '2025-10-31', '2025-11-02 12:00:00', 3, TRUE);