<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Robot-vision scenario visualization plan

Plots and short videos of the motion scenarios from the robot-vision tests ([prob-tracking-pr3-rv-tests-plan.md](prob-tracking-pr3-rv-tests-plan.md)),
to spot filter overshoot, jitter, covariance and model-probability problems.

- Branch `tdorau/prob-tracking-viz` (off `feature/prob-tracking-extracted`), separate PR into `feature/prob-tracking-extracted`.
- C++ writes JSONL data from the tests; Python turns it into PNG plots and MP4 videos.

## 1. Data capture (C++, `controller/src/robot_vision/test/support/`)

- `ScenarioRecorder.hpp` (header-only): opt-in per test with 1-2 explicit lines; writes only when `RV_SCENARIO_DIR` is set, no I/O otherwise.
- Output directory `$RV_SCENARIO_DIR/<Suite>.<Test>/<case>/`.
- `FilterRun` takes an optional recorder and records both after predict and after correct, calling `predict()` and `correct()` separately (equivalent to `track()`).
- Minimal JSON writer in the same header; no new dependency (rapidjson only exists in the tracker conan build).
- `TruthSample` gains `acceleration`, set per segment like `yawRate`.

```cpp
ScenarioRecorder rec("turn");                                    // no-op unless RV_SCENARIO_DIR is set
rec.truth(truth, {.id = 1, .category = "vehicle"});
FilterRun run(productionConfig(), &rec);
run.feed(rec.detections(observe(truth, camera), "camera"));      // pass-through, records detections
```

## 2. Files per scenario (JSONL)

All timestamps are ISO 8601 UTC with microseconds, counted from the `system_clock` epoch (`atSeconds(t)`). All records carry an object or track id, ready for more than one object.

| File                | Format                                                                                                                                                                                                                                                                               |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `groundtruth.jsonl` | Canonical GT (evaluation README). Adds optional `size`, `rotation` (heading quaternion) and `velocity`, plus `truth: {speed, yaw_rate, acceleration}`                                                                                                                                |
| `detections.jsonl`  | Canonical input, `camera-data.schema.json` from `ITEP-97104_tracker_3d_detections`: `translation`, `size`; `rotation` only from orienting sensors. Sensor id = recorder argument (identity sensor pose assumed)                                                                      |
| `tracks.jsonl`      | Canonical tracker output (`scene-data.schema.json`), combined estimate after correct; usable by `JitterEvaluator` and `DiagnosticEvaluator`                                                                                                                                          |
| `estimator.jsonl`   | Line 1 `config`: models, q, r, P0, UKF alpha/beta/kappa, transition matrix, state and measurement names. Then one `step` per phase (`predict`, `correct`, `coast`): `track_id`, `dt`, `sensor_id`, mixing matrix; combined and per-model `x`, `P` (12x12), `z_pred`, `S` (7x7), `mu` |

- The combined `S` is the association `S` (most likely model). The mixture `S` is recomputed in Python from the per-model `S`, `z_pred` and `mu`.
- Per-model `z_pred` is recorded as-is, so the shared-buffer bug (yaw review E2, F-3) stays visible until it is fixed.

## 3. Python tools (`tools/tracker/evaluation/visualization/`)

They reuse the evaluation `.venv`, `requirements.txt` and `utils/format_converters.py`; nothing new is needed (matplotlib, numpy, pandas, system `ffmpeg`).

| Module / CLI       | Purpose                                                                                                                                           |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scenario_data.py` | Loads a scenario directory into time-aligned tables per object or track; any file may be missing (e.g. real tracker output: no `estimator.jsonl`) |
| `plot_scenario.py` | Static PNGs; `--plots` selects a subset; `--run label=dir` (repeatable) overlays runs of the same scenario                                        |
| `render_video.py`  | Single run. Default: overview MP4; `--zoom <id>`: separate zoomed MP4; `--gif`, `--speed`                                                         |

Default plot set:

1. Top-down trajectory: ground truth, detections, estimate.
2. Position error (total, along-track, cross-track) with a ±2σ band from `P`.
3. Speed, heading/yaw and yaw rate: estimate vs truth.
4. Size (l, w, h): estimate vs truth vs detections.
5. Model probabilities and per-model position error.
6. Covariance: √diag `P` (position, velocity, yaw, yaw rate, size), `S_xy` ellipse area (most likely model vs mixture), min eigenvalue of `P`.
7. Consistency: NEES (x, y, vx, vy) and NIS with χ² bounds.

Plus `summary.json`: max and RMS errors after warm-up, to re-calibrate test bounds (rv tests plan §7).

Videos (matplotlib `FuncAnimation` → H.264 MP4, optional GIF):

- Overview (default): whole scene, all objects; ground-truth and estimated boxes (position, size, heading) with trails.
- Zoom (opt-in, separate file): follow camera on one object. Shows everything above plus:
  - detection box;
  - predicted (prior) position;
  - velocity arrow;
  - χ² gate ellipse from `S_xy`;
  - per-model positions;
  - optional error magnification;
  - model-probability strip with a time cursor.

## 4. Steps (one commit each)

1. Recorder and JSON writer, `TruthSample::acceleration`, recorder test (writes to a temporary directory).
2. Recording in `MotionScenarioTests` (C-7 cases, C-8, C-9).
3. `scenario_data.py` and pytest tests with small fixture files; schema validation of generated files.
4. `plot_scenario.py` with tests (smoke test, run overlay).
5. `render_video.py` with tests (smoke test on a short fixture, ffmpeg skipped if missing).
6. Docs: `visualization/README.md` (workflow: `RV_SCENARIO_DIR=... RobotVisionTests --gtest_filter=...`, then the CLIs), links from the evaluation README and the robot-vision test docs.

Verification: `make -C tracker test-robot-vision` and `tools/tracker/evaluation/run_tests.sh unit`.

## 5. Open points

- The 3D `camera-data.schema.json` is not yet on `feature/prob-tracking-extracted`. Schema validation in step 3 needs it: merge `ITEP-97104_tracker_3d_detections` first, or validate against a copy until then?
- Category per object: recorder argument (proposed) or a `category` field in `Box`?
- Out of scope: tracker-level runs (`MultipleObjectTracker`, lifecycle, association), and a scene configuration with identity-pose sensors for replaying through the Tracker service.
