
-- Table structure for table `staff`
--

DROP TABLE IF EXISTS `staff`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `staff` (
  `staff_id` int NOT NULL AUTO_INCREMENT,
  `first_name` varchar(50) NOT NULL,
  `last_name` varchar(50) NOT NULL,
  `email` varchar(100) NOT NULL,
  `grade` varchar(20) DEFAULT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` enum('Staff Member','LTSM Committee Member') NOT NULL DEFAULT 'Staff Member',
  PRIMARY KEY (`staff_id`),
  UNIQUE KEY `staff_AK1` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `staff`
--

LOCK TABLES `staff` WRITE;
/*!40000 ALTER TABLE `staff` DISABLE KEYS */;
INSERT INTO `staff` VALUES (1,'Thandi','Nkosi','g1.teacher1@example.com','Grade 1','pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(2,'James','Smith','g1.teacher2@example.com','Grade 1','pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(3,'Lerato','Mokoena','g1.teacher3@example.com','Grade 1','pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(4,'Emma','Botha','g1.teacher4@example.com','Grade 1','pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(5,'Ayesha','Jacobs','g2.teacher1@example.com','Grade 2','pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(6,'Sipho','Dlamini','g2.teacher2@example.com','Grade 2','pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(7,'Fatima','Khan','g2.teacher3@example.com','Grade 2','pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(8,'Michael','Williams','g2.teacher4@example.com','Grade 2','pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(9,'Naledi','Molefe','g3.teacher1@example.com','Grade 3','pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(10,'Daniel','Petersen','g3.teacher2@example.com','Grade 3','pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(11,'Zanele','Zulu','g3.teacher3@example.com','Grade 3','pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(12,'Rebecca','Adams','g3.teacher4@example.com','Grade 3','pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(13,'Nomsa','Khumalo','ltsm01@example.com',NULL,'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','LTSM Committee Member'),(14,'David','Naidoo','ltsm02@example.com',NULL,'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','LTSM Committee Member'),(15,'Patricia','Adams','ltsm03@example.com',NULL,'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','LTSM Committee Member'),(16,'Themba','Maseko','ltsm04@example.com',NULL,'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','LTSM Committee Member'),(17,'Grace','September','office01@example.com',NULL,'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(18,'Yusuf','Petersen','office02@example.com',NULL,'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member'),(19,'Linda','Mahlangu','office03@example.com',NULL,'pbkdf2:sha256:150000$QjP6lQp6$367d15a7aea2281fb9c909c809835573e338545a247cdb7b3683668beacbd4aa','Staff Member');
/*!40000 ALTER TABLE `staff` ENABLE KEYS */;
UNLOCK TABLES;
