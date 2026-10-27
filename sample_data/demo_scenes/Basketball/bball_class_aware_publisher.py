#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Publish person+basketball camera MQTT with class-aware NMS.

gvadetect uses class-agnostic NMS, which suppresses the basketball BB when it
overlaps the person. This sidecar reads RTSP, runs the same YOLO-World IR with
per-class NMS, and publishes scenescape/data/camera/<id> payloads.
"""

from __future__ import annotations

import argparse
import json
import ssl
import time
from datetime import datetime, timezone

import cv2
import numpy as np
import paho.mqtt.client as mqtt
from openvino import Core


LABELS = ["person", "basketball"]


def letterbox(im, new_shape=640):
  h, w = im.shape[:2]
  r = min(new_shape / h, new_shape / w)
  nh, nw = int(round(h * r)), int(round(w * r))
  resized = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_LINEAR)
  canvas = np.full((new_shape, new_shape, 3), 114, dtype=np.uint8)
  top = (new_shape - nh) // 2
  left = (new_shape - nw) // 2
  canvas[top:top + nh, left:left + nw] = resized
  return canvas, r, left, top


def nms(boxes, scores, iou_thr=0.45):
  if len(boxes) == 0:
    return []
  x1, y1, x2, y2 = boxes.T
  areas = (x2 - x1) * (y2 - y1)
  order = scores.argsort()[::-1]
  keep = []
  while order.size:
    i = order[0]
    keep.append(i)
    xx1 = np.maximum(x1[i], x1[order[1:]])
    yy1 = np.maximum(y1[i], y1[order[1:]])
    xx2 = np.minimum(x2[i], x2[order[1:]])
    yy2 = np.minimum(y2[i], y2[order[1:]])
    inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
    iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
    order = order[1:][iou <= iou_thr]
  return keep


class Detector:
  def __init__(self, xml_path: str):
    core = Core()
    self.compiled = core.compile_model(xml_path, "CPU")
    self.out = self.compiled.output(0)

  def detect(self, bgr, thr=0.25):
    h, w = bgr.shape[:2]
    canvas, r, left, top = letterbox(bgr, 640)
    x = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    p = self.compiled([x])[self.out][0]
    boxes = p[:4].T
    scores = p[4:].T
    cls = scores.argmax(1)
    conf = scores.max(1)
    m = conf >= thr
    b, s, c = boxes[m], conf[m], cls[m]
    xyxy = np.stack(
      [b[:, 0] - b[:, 2] / 2, b[:, 1] - b[:, 3] / 2,
       b[:, 0] + b[:, 2] / 2, b[:, 1] + b[:, 3] / 2], 1)
    keep = []
    for ci in range(len(LABELS)):
      idx = np.where(c == ci)[0]
      if len(idx) == 0:
        continue
      for k in nms(xyxy[idx], s[idx], 0.45):
        keep.append(idx[k])
    objects = {lab: [] for lab in LABELS}
    for k in keep:
      x1, y1, x2, y2 = xyxy[k]
      x1 = float(np.clip((x1 - left) / r, 0, w - 1))
      x2 = float(np.clip((x2 - left) / r, 0, w - 1))
      y1 = float(np.clip((y1 - top) / r, 0, h - 1))
      y2 = float(np.clip((y2 - top) / r, 0, h - 1))
      lab = LABELS[int(c[k])]
      objects[lab].append({
        "category": lab,
        "confidence": float(s[k]),
        "bounding_box_px": {
          "x": int(round(x1)), "y": int(round(y1)),
          "width": int(round(x2 - x1)), "height": int(round(y2 - y1)),
        },
      })
    return {k: v for k, v in objects.items() if v}


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--xml", required=True)
  ap.add_argument("--broker", default="broker.scenescape.intel.com")
  ap.add_argument("--port", type=int, default=1883)
  ap.add_argument("--ca", default="/run/secrets/certs/scenescape-ca.pem")
  ap.add_argument("--camera", action="append", nargs=2, metavar=("ID", "RTSP"),
                  required=True)
  ap.add_argument("--threshold", type=float, default=0.25)
  ap.add_argument("--fps", type=float, default=10.0)
  args = ap.parse_args()

  det = Detector(args.xml)
  try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
  except AttributeError:
    client = mqtt.Client()
  client.tls_set(ca_certs=args.ca, cert_reqs=ssl.CERT_REQUIRED)
  client.tls_insecure_set(True)
  client.connect(args.broker, args.port, 60)
  client.loop_start()

  caps = []
  for cam_id, url in args.camera:
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
      raise SystemExit(f"failed to open {url}")
    caps.append((cam_id, cap))

  period = 1.0 / max(args.fps, 1e-3)
  print("publishing", [c[0] for c in caps], flush=True)
  while True:
    t0 = time.time()
    for cam_id, cap in caps:
      ok, frame = cap.read()
      if not ok:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue
      objects = det.detect(frame, thr=args.threshold)
      for i, lab in enumerate(LABELS):
        for o in objects.get(lab, []):
          o["id"] = i + 1
      payload = {
        "id": cam_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "rate": args.fps,
        "objects": objects,
      }
      topic = f"scenescape/data/camera/{cam_id}"
      client.publish(topic, json.dumps(payload), qos=0)
    dt = time.time() - t0
    if dt < period:
      time.sleep(period - dt)


if __name__ == "__main__":
  main()
