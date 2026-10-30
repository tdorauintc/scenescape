<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Robot-vision scenario visualization plan

Plots and short videos of the motion scenarios from the robot-vision tests ([prob-tracking-pr3-rv-tests-plan.md](../plans/prob-tracking-pr3-rv-tests-plan.md)),
to spot filter overshoot, jitter, covariance and model-probability problems.
Visualization only: fixes are diagnosed and verified in unit tests.

- Branch `tdorau/prob-tracking-viz`, stacked on `tdorau/imm-ukf-improvements`; PR into `feature/prob-tracking-extracted` after it.
- C++ writes JSONL data from the tests; Python turns it into PNG plots and MP4 videos.
- Status: implemented (`a967511b0`..`d35057263`); workflow in `tools/tracker/evaluation/visualization/README.md`.
- Tracker-level runs (PR 4, `bf8aee1d4`): `TrackerRun` drives `MultipleObjectTracker` and the recorder writes its detections, reliable tracks and estimator steps, with the association gate in each track's config line; zoom videos draw that gate (χ² ellipse or `max_radius_m` circle; not for detections with per-detection R, see §3).

## 1. Data capture (C++, `controller/src/robot_vision/test/support/`)

- `ScenarioRecorder.hpp` (header-only): opt-in per test with 1-2 explicit lines; writes only when `RV_SCENARIO_DIR` is set, no I/O otherwise.
- Output directory `$RV_SCENARIO_DIR/<Suite>.<Test>/<case>/`.
- `FilterRun` takes an optional recorder, notified after `initialize()`, every `track()` (with the observation, so detections are recorded too) and every `coast()`; the estimator is driven as before.
- `Sensor` gains `id` (default `camera`), copied by `observe()` into `Observation::sensorId`; no `camera_id` attribute is needed since streaming fusion was removed.
- Minimal JSON writer in the same header; no new dependency (rapidjson only exists in the tracker conan build).
- `TruthSample` gains `acceleration`, set per segment like `yawRate`.
- `Box` gains `category` (`std::string_view`, keeps the presets `constexpr`): `kCar` → `vehicle`, `kPerson` → `person`.

```cpp
ScenarioRecorder rec("turn");                                    // no-op unless RV_SCENARIO_DIR is set
rec.truth(truth);                                                // object id 1; category from the truth Box
FilterRun run(productionConfig(), &rec);
run.feed(observe(truth, camera));                                // records detections and estimates
```

## 2. Files per scenario (JSONL)

All timestamps are ISO 8601 UTC with microseconds, counted from the `system_clock` epoch (`atSeconds(t)`). All records carry an object or track id, ready for more than one object.

| File                | Format                                                                                                                                                                                                                                                                      |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `groundtruth.jsonl` | Canonical GT (evaluation README). Adds optional `size`, `rotation` (heading quaternion) and `velocity`, plus `truth: {speed, yaw_rate, acceleration}`                                                                                                                       |
| `detections.jsonl`  | Canonical input, `tracker/schema/camera-data.schema.json` with 3D detections (#2050; validated against it since `5ccd64279`, before against a copy): `translation`, `size`; `rotation` only from orienting sensors. Sensor id = `Sensor::id` (identity sensor pose assumed) |
| `tracks.jsonl`      | Canonical tracker output (`scene-data.schema.json`), estimate after every `FilterRun` step; usable by `JitterEvaluator` and `DiagnosticEvaluator`                                                                                                                           |
| `estimator.jsonl`   | Line 1 `config`: models, q, r, P0, UKF alpha/beta/kappa, transition matrix, model probability limits, state and measurement names. Then one `step` per `FilterRun` step: `track_id`, model probabilities `mu`, state `x`, `P` (12x12), `z_pred`, `S` (7x7)                  |

- `x`, `P` and `mu` are the combined estimate after the step. `z_pred` and association `S` (most likely model) come from the last predict, as used for gating; null at init.

## 3. Python tools (`tools/tracker/evaluation/visualization/`)

They reuse the evaluation `.venv`, `requirements.txt`, `utils/format_converters.py` and `utils/timeline.py`; nothing new is needed (matplotlib, numpy, pandas, system `ffmpeg`).
Tracks are paired with ground-truth objects by `match_tracks()`, moved from `DiagnosticEvaluator` to `utils/tracks.py`, so real tracker output (UUID track ids) works too.

| Module / CLI       | Purpose                                                                                                                                           |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scenario_data.py` | Loads a scenario directory into time-aligned tables per object or track; any file may be missing (e.g. real tracker output: no `estimator.jsonl`) |
| `plot_scenario.py` | Static PNGs in `<dir>/plots/`; `--plots` selects a subset                                                                                         |
| `render_video.py`  | Overview MP4 in `<dir>/videos/`; each `--zoom <id>` adds a zoomed MP4; `--gif` (GIF instead of MP4), `--speed`, `--trail`, `--zoom-size`          |

Default plot set:

1. `trajectory`: top-down ground truth, detections, estimate.
2. `position_error`: total, along-track, cross-track, with a ±2σ band from `P`.
3. `speed_yaw`: speed, heading/yaw and yaw rate, estimate vs truth.
4. `size`: l, w, h, estimate vs truth vs detections.
5. `model_probability`.
6. `std_dev`: √diag `P` for position, velocity, yaw, yaw rate, size.

Videos (matplotlib animation writers → H.264 MP4 or GIF; real time, at most 30 fps, 2 s trails):

- Overview (default): whole scene, all objects; ground-truth and estimated boxes (position, size, heading) with trails.
- Zoom (opt-in, separate file): follow camera on one object. Shows everything above plus:
  - predicted position (`z_pred`);
  - velocity arrow;
  - 99% confidence ellipse of the predicted position from `S_xy` (on PR 3 not the association gate, which is a Euclidean radius; with PR 4's `position_mahalanobis` it is the gate, up to the `max_radius_m` ceiling). With per-detection R ([post-review plan](../plans/prob-tracking-post-review-plan.md#pr-7-per-detection-measurement-noise-r) item 7) a detection that carries R is gated with `(H P Hᵀ)_xy + R_xy` instead, so the ellipse is the gate only for detections without R. The recorded `S` holds the default R and `detections.jsonl` has no R, so drawing that gate needs R recorded;
  - window 4× the object's largest dimension, at least 4 m.

## 4. Steps (one commit each)

1. Recorder and JSON writer, `FilterRun` observer hook, `TruthSample::acceleration`, `Box::category`, recorder test (writes to a temporary directory).
2. Recording in `MotionScenarioTests` (C-7 cases, C-8, C-9).
3. `scenario_data.py` and pytest tests with small fixture files; schema validation of generated files (`detections.jsonl` against the Tracker 3D `camera-data.schema.json`).
   - Refactor before step 4: `DiagnosticEvaluator._match_tracks` moved unchanged to `utils/tracks.py`.
4. `plot_scenario.py` with tests (smoke test).
5. `render_video.py` with tests (smoke test on a short fixture, ffmpeg skipped if missing).
6. Docs: `visualization/README.md` (workflow: `RV_SCENARIO_DIR=... RobotVisionTests --gtest_filter=...`, then the CLIs), links from the evaluation README and the robot-vision test docs.

Verification: `make -C tracker test-robot-vision` and `tools/tracker/evaluation/run_tests.sh unit`.

## 5. Out of scope

- Filter diagnostics (prior vs posterior, per-model states, NEES / NIS, run comparison); covered by unit tests.
- A scene configuration with identity-pose sensors for replaying through the Tracker service.
- Merging `ITEP-97104_tracker_3d_detections` (merged as #2050; the schema copy was replaced by `tracker/schema/camera-data.schema.json` in `5ccd64279`).
