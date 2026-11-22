CREATE DATABASE  IF NOT EXISTS `ltsm_db` /*!40100 DEFAULT CHARACTER SET utf8mb3 */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `ltsm_db`;
-- MySQL dump 10.13  Distrib 8.0.46, for Win64 (x86_64)
--
-- Host: localhost    Database: ltsm_db
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `consumable_demand_history`
--

DROP TABLE IF EXISTS `consumable_demand_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `consumable_demand_history` (
  `resource_id` int NOT NULL,
  `history_start` date NOT NULL,
  `history_end` date NOT NULL,
  `demand_values` json NOT NULL,
  PRIMARY KEY (`resource_id`),
  KEY `fk_table2_resource1_idx` (`resource_id`),
  CONSTRAINT `fk_table2_resource1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`resource_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `consumable_demand_history`
--

LOCK TABLES `consumable_demand_history` WRITE;
/*!40000 ALTER TABLE `consumable_demand_history` DISABLE KEYS */;
INSERT INTO `consumable_demand_history` VALUES (1,'2022-12-01','2025-11-30','[136, 140, 144]'),(2,'2022-12-01','2025-11-30','[136, 140, 144]'),(3,'2022-12-01','2025-11-30','[136, 140, 144]'),(4,'2022-12-01','2025-11-30','[136, 140, 144]'),(5,'2022-12-01','2025-11-30','[136, 140, 144]'),(6,'2022-12-01','2025-11-30','[136, 140, 144]'),(7,'2022-12-01','2025-11-30','[136, 140, 144]'),(8,'2022-12-01','2025-11-30','[136, 140, 144]'),(9,'2022-12-01','2025-11-30','[136, 140, 144]'),(10,'2022-12-01','2025-11-30','[136, 140, 144]'),(11,'2022-12-01','2025-11-30','[136, 140, 144]'),(12,'2022-12-01','2025-11-30','[136, 140, 144]'),(13,'2022-12-01','2025-11-30','[136, 140, 144]'),(14,'2022-12-01','2025-11-30','[136, 140, 144]'),(15,'2022-12-01','2025-11-30','[136, 140, 144]'),(16,'2022-12-01','2025-11-30','[136, 140, 144]'),(17,'2022-12-01','2025-11-30','[136, 140, 144]'),(18,'2022-12-01','2025-11-30','[136, 140, 144]'),(19,'2022-12-01','2025-11-30','[136, 140, 144]'),(20,'2022-12-01','2025-11-30','[136, 140, 144]'),(21,'2022-12-01','2025-11-30','[136, 140, 144]'),(22,'2022-12-01','2025-11-30','[136, 140, 144]'),(23,'2022-12-01','2025-11-30','[136, 140, 144]'),(24,'2022-12-01','2025-11-30','[136, 140, 144]'),(25,'2022-12-01','2025-11-30','[136, 140, 144]'),(26,'2022-12-01','2025-11-30','[136, 140, 144]'),(27,'2022-12-01','2025-11-30','[136, 140, 144]'),(28,'2026-01-01','2026-06-30','[10, 9, 20, 10, 15, 20]'),(29,'2026-01-01','2026-06-30','[20, 25, 10, 8, 7, 10]'),(30,'2026-01-01','2026-06-30','[2, 3, 2, 4, 3, 4]'),(31,'2026-01-01','2026-06-30','[2, 1, 3, 2, 2, 3]'),(32,'2026-01-01','2026-06-30','[2, 3, 2, 4, 3, 3]'),(33,'2026-01-01','2026-06-30','[3, 4, 3, 5, 4, 5]'),(34,'2026-01-01','2026-06-30','[2, 3, 2, 4, 3, 4]'),(35,'2026-01-01','2026-06-30','[3, 4, 3, 5, 4, 5]'),(36,'2026-01-01','2026-06-30','[4, 5, 4, 6, 5, 6]'),(37,'2026-01-01','2026-06-30','[3, 4, 3, 5, 4, 5]'),(63,'2026-01-01','2026-06-30','[1, 2, 1, 2, 1, 2]'),(64,'2026-01-01','2026-06-30','[3, 4, 3, 5, 4, 5]');
/*!40000 ALTER TABLE `consumable_demand_history` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `resource`
--

DROP TABLE IF EXISTS `resource`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `resource` (
  `resource_id` int NOT NULL AUTO_INCREMENT,
  `resource_name` varchar(100) NOT NULL,
  `category` enum('consumable','non-consumable','laptop','printer') NOT NULL,
  `grade` varchar(20) DEFAULT NULL,
  `quantity owned` int NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `unit_of_measure` varchar(45) NOT NULL,
  `unit_price` decimal(10,2) DEFAULT NULL,
  `review_policy` enum('six_month','annual') DEFAULT NULL,
  PRIMARY KEY (`resource_id`)
) ENGINE=InnoDB AUTO_INCREMENT=65 DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `resource`
--

LOCK TABLES `resource` WRITE;
/*!40000 ALTER TABLE `resource` DISABLE KEYS */;
INSERT INTO `resource` VALUES (1,'Grade 3 DBE blue book – Maths (English), Vol. 1','consumable','Grade 3',25,'DBE workbook','books',80.00,'annual'),(2,'Grade 2 DBE blue book – Maths (English), Vol. 1','consumable','Grade 2',25,'DBE workbook','books',80.00,'annual'),(3,'Grade 1 DBE blue book – Maths (English), Vol. 1','consumable','Grade 1',25,'DBE workbook','books',80.00,'annual'),(4,'Grade 3 DBE blue book – English','consumable','Grade 3',25,'DBE workbook','books',80.00,'annual'),(5,'Grade 2 DBE blue book – English','consumable','Grade 2',25,'DBE workbook','books',80.00,'annual'),(6,'Grade 1 DBE blue book – English','consumable','Grade 1',25,'DBE workbook','books',80.00,'annual'),(7,'Grade 3 DBE blue book – Afrikaans','consumable','Grade 3',25,'DBE workbook','books',80.00,'annual'),(8,'Grade 2 DBE blue book – Afrikaans','consumable','Grade 2',25,'DBE workbook','books',80.00,'annual'),(9,'Grade 1 DBE blue book – Afrikaans','consumable','Grade 1',25,'DBE workbook','books',80.00,'annual'),(10,'Grade 3 DBE blue book – LO','consumable','Grade 3',25,'DBE workbook','books',80.00,'annual'),(11,'Grade 2 DBE blue book – LO','consumable','Grade 2',25,'DBE workbook','books',80.00,'annual'),(12,'Grade 1 DBE blue book – LO','consumable','Grade 1',25,'DBE workbook','books',80.00,'annual'),(13,'Grade 3 activity book – Maths','consumable','Grade 3',25,'Learner activity book','books',50.00,'annual'),(14,'Grade 2 activity book – Maths','consumable','Grade 2',25,'Learner activity book','books',50.00,'annual'),(15,'Grade 1 activity book – Maths','consumable','Grade 1',25,'Learner activity book','books',50.00,'annual'),(16,'Grade 3 activity book – English','consumable','Grade 3',25,'Learner activity book','books',50.00,'annual'),(17,'Grade 2 activity book – English','consumable','Grade 2',25,'Learner activity book','books',50.00,'annual'),(18,'Grade 1 activity book – English','consumable','Grade 1',25,'Learner activity book','books',50.00,'annual'),(19,'Grade 3 activity book – Afrikaans','consumable','Grade 3',25,'Learner activity book','books',50.00,'annual'),(20,'Grade 2 activity book – Afrikaans','consumable','Grade 2',25,'Learner activity book','books',50.00,'annual'),(21,'Grade 1 activity book – Afrikaans','consumable','Grade 1',25,'Learner activity book','books',50.00,'annual'),(22,'Grade 3 activity book – LO','consumable','Grade 3',25,'Learner activity book','books',50.00,'annual'),(23,'Grade 2 activity book – LO','consumable','Grade 2',25,'Learner activity book','books',50.00,'annual'),(24,'Grade 1 activity book – LO','consumable','Grade 1',25,'Learner activity book','books',50.00,'annual'),(25,'Grade 3 learner stationery pack','consumable','Grade 3',25,'One pack per learner','packs',140.00,'annual'),(26,'Grade 2 learner stationery pack','consumable','Grade 2',25,'One pack per learner','packs',140.00,'annual'),(27,'Grade 1 learner stationery pack','consumable','Grade 1',25,'One pack per learner','packs',140.00,'annual'),(28,'Paper','consumable',NULL,18,'A4 copier paper for shared printing','Ream of 500 sheets',140.00,'six_month'),(29,'Sellotape','consumable',NULL,22,'Clear adhesive tape','Roll',20.00,'six_month'),(30,'Glue','consumable',NULL,6,'Glue sticks for classroom use','Box of 12 sticks',120.00,'six_month'),(31,'Elastic bands','consumable',NULL,10,'Assorted elastic bands','Pack of 100',25.00,'six_month'),(32,'Erasers','consumable',NULL,8,'White pencil erasers','Box of 20',74.50,'six_month'),(33,'HB pencils','consumable',NULL,9,'HB graphite pencils','Box of 12',48.50,'six_month'),(34,'Clutch-pencil lead','consumable',NULL,12,'0.5 mm HB refill leads','Tube of 12 leads',22.50,'six_month'),(35,'Staples','consumable',NULL,15,'Standard 26/6 staples','Box of 1,000',18.50,'six_month'),(36,'Whiteboard markers','consumable',NULL,10,'Assorted dry-erase markers','Pack of 4',64.50,'six_month'),(37,'Red marking pens','consumable',NULL,7,'Red pens for marking','Box of 12',69.50,'six_month'),(38,'Laptop type A','laptop',NULL,5,'Reusable school resource for borrowing and returning','units',NULL,NULL),(39,'Laptop type B','laptop',NULL,5,'Reusable school resource for borrowing and returning','units',NULL,NULL),(40,'Printer A','printer',NULL,1,'Reusable school resource for borrowing and returning','units',NULL,NULL),(41,'Printer B','printer',NULL,1,'Reusable school resource for borrowing and returning','units',NULL,NULL),(42,'Printer C','printer',NULL,1,'Reusable school resource for borrowing and returning','units',NULL,NULL),(43,'Abacus','non-consumable','Grade 1',200,'Reusable school resource for borrowing and returning','units',NULL,NULL),(44,'Counting blocks','non-consumable','Grade 1',4,'Reusable school resource for borrowing and returning','sets',NULL,NULL),(45,'Letter tiles','non-consumable','Grade 1',4,'Reusable school resource for borrowing and returning','sets',NULL,NULL),(46,'Geometric shapes','non-consumable','Grade 1',4,'Reusable school resource for borrowing and returning','sets',NULL,NULL),(47,'Number cards','non-consumable','Grade 1',4,'Reusable school resource for borrowing and returning','sets',NULL,NULL),(48,'Geometric shapes','non-consumable','Grade 2',4,'Reusable school resource for borrowing and returning','sets',NULL,NULL),(49,'Teaching clock','non-consumable','Grade 2',4,'Reusable school resource for borrowing and returning','units',NULL,NULL),(50,'Base-ten blocks','non-consumable','Grade 2',4,'Reusable school resource for borrowing and returning','sets',NULL,NULL),(51,'Number line board','non-consumable','Grade 2',4,'Reusable school resource for borrowing and returning','units',NULL,NULL),(52,'Play money','non-consumable','Grade 2',4,'Reusable school resource for borrowing and returning','sets',NULL,NULL),(53,'Fraction pieces','non-consumable','Grade 3',4,'Reusable school resource for borrowing and returning','sets',NULL,NULL),(54,'Balance scale','non-consumable','Grade 3',2,'Reusable school resource for borrowing and returning','units',NULL,NULL),(55,'Teaching clock','non-consumable','Grade 3',4,'Reusable school resource for borrowing and returning','units',NULL,NULL),(56,'Measuring jugs','non-consumable','Grade 3',4,'Reusable school resource for borrowing and returning','sets',NULL,NULL),(57,'Metre ruler','non-consumable','Grade 3',4,'Reusable school resource for borrowing and returning','units',NULL,NULL),(58,'Small whiteboard','non-consumable',NULL,12,'Reusable school resource for borrowing and returning','units',NULL,NULL),(59,'Teaching clock','non-consumable','Grade 1',4,'Reusable school resource for borrowing and returning','units',NULL,NULL),(60,'Bright Steps Life Skills Guide - Grade 1','non-consumable','Grade 1',160,'Reusable school resource for borrowing and returning','books',NULL,NULL),(61,'Bright Steps Life Skills Guide - Grade 2','non-consumable','Grade 2',160,'Reusable school resource for borrowing and returning','books',NULL,NULL),(62,'Bright Steps Life Skills Guide - Grade 3','non-consumable','Grade 3',160,'Reusable school resource for borrowing and returning','books',NULL,NULL),(63,'Printer ink cartridge','consumable',NULL,6,'Replacement ink cartridge for school printers','cartridges',350.00,'six_month'),(64,'Prestik','consumable',NULL,10,'Reusable adhesive putty for classroom displays','packs',25.00,'six_month');
/*!40000 ALTER TABLE `resource` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-11-22  8:37:35
