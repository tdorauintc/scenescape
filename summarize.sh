#!/bin/bash

DOCKER_LOGS="autocalibration-build.log controller-build.log percebro-build.log scenescape-broker-build.log scenescape-build.log scenescape-interface-build.log scenescape-model-installer-img-build.log"

TEMP_FILE=$(mktemp)
OUTPUT=scenescape-build-summary.txt

for logfile in $DOCKER_LOGS; do
    echo "==================== $logfile ====================" >> $TEMP_FILE
    echo >> $TEMP_FILE
    python3 parse-docker-log.py $logfile >> $TEMP_FILE
    echo >> $TEMP_FILE
done

echo "==================== Summary ====================" > $OUTPUT
cat $TEMP_FILE | grep 'build time' | awk '{sum += $5} END {print "Total build time[s]:", sum}' >> $OUTPUT
cat $TEMP_FILE | grep 'build time' | sort -r -k5,5n >> $OUTPUT
echo >> $OUTPUT
cat $TEMP_FILE >> $OUTPUT

