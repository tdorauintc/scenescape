#!/bin/bash

for folder in autocalibration controller manager percebro; do
  python3 prune_requirements.py "make -C $folder" $folder/requirements-buildtime.txt $folder/requirements-runtime.txt
done
