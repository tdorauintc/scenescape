#!/bin/bash

make -C docker scene_common
time make -C controller/docker > controller-build.log 2>&1
SUMMARY_FILE=controller-build-summary-$(date +"%Y-%m-%d_%H-%M-%S").txt
python3 parse-docker-log.py controller-build.log > ${SUMMARY_FILE}
docker images | grep scenescape-controller >> ${SUMMARY_FILE}
echo "=======================================" >> ${SUMMARY_FILE}
cat controller-build.log >> ${SUMMARY_FILE}
rm controller-build.log
echo "Results written to ${SUMMARY_FILE}"
