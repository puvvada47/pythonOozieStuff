-- Meta data Database and Table preparation
CREATE DATABASE IF NOT EXISTS `${hivevar:database_meta}`;
DROP TABLE IF EXISTS `${database_meta}`.`${hivevar:table_meta}`;

DROP DATABASE IF EXISTS `${hivevar:database_tmp_data}` cascade;
-- Temporary Data Database Creation
CREATE DATABASE IF NOT EXISTS `${hivevar:database_tmp_data}`;

-- Create Count Database
CREATE DATABASE IF NOT EXISTS `${hivevar:database_summary}`;

-- Drop the Count table if exist
DROP TABLE IF EXISTS `${hivevar:database_summary}`.`${hivevar:table_summary}`;

-- Create Count Table
CREATE table IF NOT EXISTS `${hivevar:database_summary}`.`${hivevar:table_summary}` (table_name string, source_count double, target_count double) STORED AS TEXTFILE;


DROP DATABASE IF EXISTS `${hivevar:database_data}` cascade;
-- Data Database preparation
CREATE DATABASE IF NOT EXISTS `${hivevar:database_data}`;


