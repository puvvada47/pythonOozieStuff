#!/bin/bash
hdfs dfs -rm -r -f /user/e032_s_dp-de-e-dp/oozie-initial-load-ICE/
hdfs dfs -mkdir -p /user/e032_s_dp-de-e-dp/oozie-initial-load-ICE/
hdfs dfs -put -f * /user/e032_s_dp-de-e-dp/oozie-initial-load-ICE/
output=`./oozie.sh -config job.properties -run`
echo ${output}
jobid=$(echo ${output} | tail -1 | sed "s/job: //")
echo "Use following command to:"
echo "	See job info     :
./oozie.sh -info ${jobid}"
echo "	Watch job info   :
watch -n 5 "./oozie.sh -info ${jobid} | tail -n50""
echo "	Kill the job     :
./oozie.sh -kill ${jobid}"
echo "Advanced job commands to:"
echo "	Re-run failed nodes - only for table reload:
./oozie.sh -rerun ${jobid} -Doozie.wf.rerun.failnodes=true"
echo "	Re-run datagen only:
./rerun-datagen.sh ${jobid}"
