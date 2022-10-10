#!/bin/bash
export jdbcUrl=$1
export hive_tbl_names=$2
export hive_database_4_metadata=$3
export hive_table_4_metadata=$4
export hive_database_4_data=$5
export hdfs_base_location=$6

rm hive_create_tables.hql
rm generate_create_table_statment.hql

hdfs dfs -get ${hdfs_base_location}/scripts/generate_create_table_statment.hql

echo "use ${hive_database_4_data};" >> hive_create_tables.hql

for tbl_name in $(echo $hive_tbl_names|sed "s/,/ /g")
do

beeline -u "${jdbcUrl}" -d org.apache.hive.jdbc.HiveDriver -a delegationToken --silent=true --showHeader=false --outputformat=dsv -f generate_create_table_statment.hql --hivevar v_tbl_name=${tbl_name} --hivevar v_db_name=${hive_database_4_metadata} --hivevar v_metatable_name=${hive_table_4_metadata} >> hive_create_tables.hql

done

beeline -u "${jdbcUrl}" -d org.apache.hive.jdbc.HiveDriver -a delegationToken -f hive_create_tables.hql

hdfs dfs -put -f hive_create_tables.hql ${hdfs_base_location}/scripts/

rm generate_create_table_statment.hql
rm hive_create_tables.hql
