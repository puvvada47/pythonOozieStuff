#!/bin/bash

# Example:
# ./oozie.sh -info <oozie_job_id>      - job progress status
# One can combine with watch command to update automatically
# watch -n 5 "./oozie.sh -info <oozie_job_id> |tail -n50" 

# watch -n 5 "./oozie.sh -info <oozie_job_id> | tail -n50"

oozie job -oozie https://depuasdhb201.epu.corpintra.net:11443/oozie $@

