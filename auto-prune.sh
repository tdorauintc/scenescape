#!/bin/bash

for folder in controller manager; do
  python3 prune_requirements.py "make -C $folder" $folder/requirements-buildtime.txt > ../prune-$folder.log 2>&1
done
