
-- Drop the TMP table if exist
 DROP TABLE IF EXISTS `${database_summary}`.`${table_summary_tmp}`;
 DROP TABLE IF EXISTS `${database_summary}`.`${module_name}_RESULT`;


-- Create Temp Table to get the Table Count with Table Name
  CREATE table IF NOT EXISTS `${database_summary}`.`${table_summary_tmp}` (count double, table_name string);

-- Convert Text table to ORC
  CREATE TABLE `${database_summary}`.`${module_name}_RESULT` AS SELECT * FROM `${database_summary}`.`${table_summary}`;

-- Data Tables preparation (Auto-Generated)
-- PLACEHOLDER

-- Merge TMP table into ACTUAL COUNT TABLE

   MERGE INTO `${database_summary}`.`${module_name}_RESULT` USING `${database_summary}`.`${table_summary_tmp}` tmp ON `${module_name}_RESULT`.table_name=tmp.table_name WHEN MATCHED THEN UPDATE SET target_count=tmp.count;

-- Drop the txt table
   DROP TABLE IF EXISTS `${database_summary}`.`${table_summary}`;
