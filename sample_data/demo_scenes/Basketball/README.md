<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Basketball demo

Stairs-style single-scene demo for evaluating **3D basketball tracking** (frustum
Gaussian → observation conditioning → probabilistic tracker) against monocular
metric depth (Depth Anything V2).

## Contents

| Path | Purpose |
|------|---------|
| `video/cam{1,2}.mp4` | Concatenated set-1 + set-2 clips (1280×720 @ 15 fps, ~78 s) |
| `Basketball.zip` | Scene import (placeholder floor map; cameras `bball-cam1` / `bball-cam2`, uncalibrated) |
| `basketball-config.json` | DL Streamer pipelines (YOLO-World person + basketball) |
| `compose.basketball-video.yml` | Private mediaserver + ffmpeg loopers + DL Streamer |
| `models/yolov8s-worldv2-person-basketball/` | OpenVINO IR + `yolo_v8` model-proc |
| `object-library.json` | Person + basketball Asset3D priors (FREE_3D; no `project_to_map`) |

**Not included:** Retail / Queuing scenes or pipelines.

## Start

```bash
SUPASS=<password> make demo-basketball
```

This brings up core SceneScape **plus the mapping profile** (needed to build the
map and calibrate cameras), imports only the Basketball scene, and starts the
Basketball video source. It does **not** start Retail/Queuing mediaserver or
pipelines.

Stop with `make demo-close`.

## Map + calibration (required once)

The shipped zip uses a placeholder floor PNG and approximate intrinsics — there
are no extrinsics. After `demo-basketball` is up:

1. Open the Basketball scene in the UI (3D).
2. Set calibration type to **Markerless** if not already.
3. Capture frames from `bball-cam1` / `bball-cam2` (or use the mapping-service
   reconstruction flow) to generate the mesh and auto-calibrate poses.
4. Confirm the scene controller is subscribed to
   `scenescape/data/camera/bball-cam{1,2}`.

Observation conditioning is gated on scene name `Basketball` (same allow-list
path as Stairs).

## Class-aware detection (basketball + person)

`gvadetect` applies **class-agnostic** NMS, so the basketball box is often
suppressed when it overlaps the person. For live ball tracking, stop the
DLStreamer pipeline instances and run the OpenVINO sidecar (class-aware NMS):

```bash
# after demo-basketball is up and pipelines are healthy:
ids=$(docker exec scenescape-basketball-video-1 \
  curl -s http://localhost:8080/pipelines/status | python3 -c \
  'import sys,json; print(" ".join(x["id"] for x in json.load(sys.stdin)))')
for id in $ids; do
  docker exec scenescape-basketball-video-1 curl -s -X DELETE "http://localhost:8080/pipelines/$id"
done
docker cp sample_data/demo_scenes/Basketball/bball_class_aware_publisher.py \
  scenescape-basketball-video-1:/tmp/bball_class_aware_publisher.py
docker exec -d scenescape-basketball-video-1 python3 -u /tmp/bball_class_aware_publisher.py \
  --xml /home/pipeline-server/models/public/yolov8s-worldv2-person-basketball/yolov8s-worldv2-person-basketball.xml \
  --ca /run/secrets/certs/scenescape-ca.pem \
  --camera bball-cam1 rtsp://mediaserver:8554/bball-cam1 \
  --camera bball-cam2 rtsp://mediaserver:8554/bball-cam2 \
  --threshold 0.25 --fps 8
```

## Frustum vs DA-V2 depth compare

```bash
PYTHONPATH=scene_common/src tests/.venv/bin/python tmp_bball_dav2_compare.py \
  --cases-json tmp_zverify_out/bball_cases.json \
  --out tmp_zverify_out/bball_mono_depth_compare.json
```

## Regenerate YOLO-World IR (optional)

If the OpenVINO tree is missing, with corporate proxy env loaded:

```bash
set -a && . ./.cursor_proxy.env && set +a
# see models/prepare_yolo_world.sh
bash sample_data/demo_scenes/Basketball/models/prepare_yolo_world.sh
```

## DA-V2 comparison

Reuse the Stairs offline method (`tmp_zverify_mono_depth_compare.py`): same
detector BBs → frustum `depth_est` vs Depth-Anything-V2-Metric-Indoor median in
the BB core → world Z via camera pose.
