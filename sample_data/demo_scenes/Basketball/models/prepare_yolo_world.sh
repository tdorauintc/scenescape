#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Export Ultralytics YOLO-Worldv2 OpenVINO IR with classes {person, basketball}.
# Requires network + corporate proxy (source .cursor_proxy.env first).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/yolov8s-worldv2-person-basketball"
VENV="${YOLO_WORLD_VENV:-/tmp/yolo-world-venv}"

if [[ -f "${ROOT}/.cursor_proxy.env" ]]; then
  # shellcheck disable=SC1091
  set -a && . "${ROOT}/.cursor_proxy.env" && set +a
fi

python3 -m venv "${VENV}"
"${VENV}/bin/pip" install -q --upgrade pip
"${VENV}/bin/pip" install -q ultralytics openvino

mkdir -p "$(dirname "${DEST}")"
"${VENV}/bin/python" - <<PY
from pathlib import Path
from ultralytics import YOLOWorld

dest = Path("${DEST}")
dest.mkdir(parents=True, exist_ok=True)
model = YOLOWorld("yolov8s-worldv2.pt")
model.set_classes(["person", "basketball"])
pt = dest.parent / "yolov8s-worldv2-person-basketball.pt"
model.save(str(pt))
export_dir = Path(model.export(format="openvino", imgsz=640, dynamic=False))
# Ultralytics writes <stem>_openvino_model next to the .pt
if dest.exists():
  import shutil
  shutil.rmtree(dest)
export_dir.rename(dest)
print("OpenVINO IR at", dest)
print("names", model.names)
PY

# Ensure model-proc sits beside the IR (compose bind-mounts this directory)
PROC_SRC="$(dirname "${BASH_SOURCE[0]}")/yolov8s-worldv2-person-basketball/yolo-world-person-basketball.json"
if [[ ! -f "${DEST}/yolo-world-person-basketball.json" && -f "${PROC_SRC}" ]]; then
  cp "${PROC_SRC}" "${DEST}/yolo-world-person-basketball.json"
fi

echo "DONE: ${DEST}"
