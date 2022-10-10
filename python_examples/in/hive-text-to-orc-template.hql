-- Meta data table convert TEXT to ORC
CREATE TABLE `${database_meta}`.`${table_meta}_tmp` AS SELECT * FROM `${database_meta}`.`${table_meta}`;
DROP TABLE IF EXISTS `${database_meta}`.`${table_meta}`;
CREATE TABLE `${database_meta}`.`${table_meta}` AS SELECT * FROM `${database_meta}`.`${table_meta}_tmp`;
DROP TABLE IF EXISTS `${database_meta}`.`${table_meta}_tmp`;

--Database creation which holds actual data
CREATE DATABASE IF NOT EXISTS `${database_data}`;

-- Data Table convert TEXT to ORC (Auto-Generated)
-- PLACEHOLDER

--Drop the temporary database
DROP DATABASE IF EXISTS `${database_tmp_data}` CASCADE;


