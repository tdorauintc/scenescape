#!/bin/bash

folder=$1
container=$2

if [ -z "$folder" ] || [ -z "$container" ]; then
    echo "Usage: $0 <folder> <container>"
    exit 1
fi

export SUPASS=admin

set -e -o pipefail

running_containers=$(docker ps -q)
if [ -n "$running_containers" ]; then
  echo "Stopping running containers..."
  docker stop $running_containers
fi
git clean -fdx
make FOLDERS="$folder"
make -C docker secrets
make demo
sleep 30
container_id=$(docker ps | grep $container | awk '{ print $1 }')
if [ -n "$container_id" ]; then
  errors=$(docker logs "$container_id" 2>&1 | tee $folder-run.log | grep -i error || true)
else
  echo "Container $container not found."
  exit 1
fi
restarts=$(docker ps | grep "$container_id" | grep Restart || true)

docker compose down

if [ -n "$errors" ] || [ -n "$restarts" ]; then
  echo "Errors found in logs or container restarts detected:"
  echo "Errors:"
  echo "$errors"
  echo "Restarts:"
  echo "$restarts"
  exit 1
else
  echo "No errors found and no restarts detected."
fi
