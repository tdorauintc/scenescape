<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Robot-vision scenario visualization plan

Plots and short videos of the motion scenarios from the robot-vision tests ([prob-tracking-pr3-rv-tests-plan.md](prob-tracking-pr3-rv-tests-plan.md)),
to spot filter overshoot, jitter, covariance and model-probability problems.
Visualization only: fixes are diagnosed and verified in unit tests.

- Branch `tdorau/prob-tracking-viz`, stacked on `tdorau/imm-ukf-improvements`; PR into `feature/prob-tracking-extracted` after it.
- C++ writes JSONL data from the tests; Python turns it into PNG plots and MP4 videos.

## 1. Data capture (C++, `controller/src/robot_vision/test/support/`)

- `ScenarioRecorder.hpp` (header-only): opt-in per test with 1-2 explicit lines; writes only when `RV_SCENARIO_DIR` is set, no I/O otherwise.
- Output directory `$RV_SCENARIO_DIR/<Suite>.<Test>/<case>/`.
- `FilterRun` takes an optional recorder, notified after `initialize()`, every `track()` and every `coast()`; the estimator is driven as before.
- Minimal JSON writer in the same header; no new dependency (rapidjson only exists in the tracker conan build).
- `TruthSample` gains `acceleration`, set per segment like `yawRate`.
- `Box` gains `category` (`std::string_view`, keeps the presets `constexpr`): `kCar` → `vehicle`, `kPerson` → `person`.

```cpp
ScenarioRecorder rec("turn");                                    // no-op unless RV_SCENARIO_DIR is set
rec.truth(truth, 1);                                             // object id; category from the truth Box
FilterRun run(productionConfig(), &rec);
run.feed(rec.detections(observe(truth, camera), "camera"));      // pass-through, records detections
```

## 2. Files per scenario (JSONL)

All timestamps are ISO 8601 UTC with microseconds, counted from the `system_clock` epoch (`atSeconds(t)`). All records carry an object or track id, ready for more than one object.

| File                | Format                                                                                                                                                                                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `groundtruth.jsonl` | Canonical GT (evaluation README). Adds optional `size`, `rotation` (heading quaternion) and `velocity`, plus `truth: {speed, yaw_rate, acceleration}`                                                                                                         |
| `detections.jsonl`  | Canonical input, `camera-data.schema.json` from `ITEP-97104_tracker_3d_detections` (validated against a copy, branch not merged): `translation`, `size`; `rotation` only from orienting sensors. Sensor id = recorder argument (identity sensor pose assumed) |
| `tracks.jsonl`      | Canonical tracker output (`scene-data.schema.json`), estimate after every `FilterRun` step; usable by `JitterEvaluator` and `DiagnosticEvaluator`                                                                                                             |
| `estimator.jsonl`   | Line 1 `config`: models, q, r, P0, UKF alpha/beta/kappa, transition matrix, model probability limits, state and measurement names. Then one `step` per `FilterRun` step: `track_id`, model probabilities `mu`, state `x`, `P` (12x12), `z_pred`, `S` (7x7)    |

- `x`, `P` and `mu` are the combined estimate after the step. `z_pred` and association `S` (most likely model) come from the last predict, as used for gating; null at init.

## 3. Python tools (`tools/tracker/evaluation/visualization/`)

They reuse the evaluation `.venv`, `requirements.txt` and `utils/format_converters.py`; nothing new is needed (matplotlib, numpy, pandas, system `ffmpeg`).

| Module / CLI       | Purpose                                                                                                                                           |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scenario_data.py` | Loads a scenario directory into time-aligned tables per object or track; any file may be missing (e.g. real tracker output: no `estimator.jsonl`) |
| `plot_scenario.py` | Static PNGs; `--plots` selects a subset                                                                                                           |
| `render_video.py`  | Single run. Default: overview MP4; `--zoom <id>`: separate zoomed MP4; `--gif`, `--speed`                                                         |

Default plot set:

1. Top-down trajectory: ground truth, detections, estimate.
2. Position error (total, along-track, cross-track) with a ±2σ band from `P`.
3. Speed, heading/yaw and yaw rate: estimate vs truth.
4. Size (l, w, h): estimate vs truth vs detections.
5. Model probabilities.
6. Standard deviations √diag `P`: position, velocity, yaw, yaw rate, size.

Videos (matplotlib `FuncAnimation` → H.264 MP4, optional GIF):

- Overview (default): whole scene, all objects; ground-truth and estimated boxes (position, size, heading) with trails.
- Zoom (opt-in, separate file): follow camera on one object. Shows everything above plus:
  - predicted position (`z_pred`);
  - velocity arrow;
  - χ² gate ellipse from `S_xy`.

## 4. Steps (one commit each)

1. Recorder and JSON writer, `FilterRun` observer hook, `TruthSample::acceleration`, `Box::category`, recorder test (writes to a temporary directory).
2. Recording in `MotionScenarioTests` (C-7 cases, C-8, C-9).
3. `scenario_data.py` and pytest tests with small fixture files; schema validation of generated files (`detections.jsonl` against a copy of the 3D `camera-data.schema.json` in the visualization tests).
4. `plot_scenario.py` with tests (smoke test).
5. `render_video.py` with tests (smoke test on a short fixture, ffmpeg skipped if missing).
6. Docs: `visualization/README.md` (workflow: `RV_SCENARIO_DIR=... RobotVisionTests --gtest_filter=...`, then the CLIs), links from the evaluation README and the robot-vision test docs.

Verification: `make -C tracker test-robot-vision` and `tools/tracker/evaluation/run_tests.sh unit`.

## 5. Out of scope

- Filter diagnostics (prior vs posterior, per-model states, NEES / NIS, run comparison); covered by unit tests.
- Tracker-level runs (`MultipleObjectTracker`, lifecycle, association).
- A scene configuration with identity-pose sensors for replaying through the Tracker service.
- Merging `ITEP-97104_tracker_3d_detections`; the schema copy is replaced by `tracker/schema/camera-data.schema.json` once it lands.
