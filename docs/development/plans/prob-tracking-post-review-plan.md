<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# `feature/prob-tracking` branch split plan

## High level details

- Branch: `feature/prob-tracking` @ `188c40e79`, split into PRs 1–8, so the accuracy and performance impact of each can be evaluated separately.
- PRs: #1979, #2028, #2050, #2036 (merged to `main`); #2056 (merged into PR 3 before it); #2037, #2109, #2129 (open). Branch stack: [Details / Context](#context-1).
- Status: PRs 1, 2, 3 and 6 done; PRs 4, 5 and 7 in progress; PR 8 not started.

### Context

- "PR N" (also "step N" or "item N" in other documents) is item N of this plan.
- PRs 1, 2, 3 and 6 are on `main`; PRs 4 → 5 → 7 are feature branches stacked on `main`; PR 8 evaluates the stack and merges it to `main`.
- Review findings are cited by the short names in [Related documents](#related-documents), e.g. "prob review G9", "yaw review E2", "z review Z1", "delta 9.1", "baseline 9.4".
- This plan and the [tuning guide](prob-tracking-imm-tuning.md) are the single source of truth: each task in [Details](#details) carries the context needed to do it. The other documents are kept for back-tracking only; finding IDs point to them, and C-n (coverage test), F-n (fix + verification test) and E-n (evaluation) to the PR 3 test plan, which keeps the test-level history (mechanisms, before / after values, sweeps).
- robot_vision fixes are test-first: the failing test lands first, then the fix with before / after values in its commit message. Verify with `make -C tracker test-robot-vision`, `RobotVisionTests --gtest_filter=...` while iterating, and `RV_SCENARIO_DIR` to record scenarios. Build from a clean build directory: one configured from `main` keeps `RV_CXX_STANDARD=17` in its cache, and the tests fail on C++20 features.
- Impact evaluation: Tracker Evaluation black-box runs from `tools/tracker/evaluation/` (`python -m run_black_box_evaluation`, `--dataset wildtrack` for Wildtrack) cover Controller Immediate, Controller time-chunking and Tracker Service; the `association` block is in `pipeline_configs/black_box_*/config/*.json`. Compare HOTA, IDF1, IDSW, DIST_T, rms_jerk and acceleration_variance with the base branch.

### Related documents

- [Tuning guide](prob-tracking-imm-tuning.md): IMM-UKF tuning knowledge (terms, knobs, KPIs, trade-offs) and the prerequisites before tuning; single source of truth with this plan.
- [ADR-0017](../../adr/0017-probabilistic-tracking-association.md) and [design doc](../../design/probabilistic-tracking-association.md): product docs with the probabilistic association decisions and phases; PR 4, 5 and 7 update them.

Deprecated, for back-tracking only; the tasks below do not depend on them:

- [PR 3 test plan](../deprecated/prob-tracking-pr3-rv-tests-plan.md): C-n, F-n, E-n; mechanisms, before / after values and sweeps of the PR 3 tests and fixes.
- [Visualization plan](../deprecated/prob-tracking-viz-plan.md): design of the scenario recorder, plots and videos (#2086); workflow in `tools/tracker/evaluation/visualization/README.md`.
- [prob review](../deprecated/pr-review-probabilistic-tracking.md): review of `feature/prob-tracking` vs `main`; issues "N", coverage gaps "GN".
- [yaw review](../deprecated/pr-review-yaw-fusion.md): review of the yaw fusion commit (#1958); findings "N", related issues "EN".
- [z review](../deprecated/pr-review-tracking-z-axis.md): review of non-planar Z / `vz` tracking; findings "ZN", "EN", "IN".
- [baseline](../deprecated/robot-vision-tracking-algorithms.md): robot-vision tracking algorithms on `main`; Section 9 items "9.N".
- [delta](../deprecated/robot-vision-tracking-prob-tracking-delta.md): robot-vision changes in `feature/prob-tracking`; Section 9 items "9.N".

## Tasks Done

1. [PR 1](#pr-1-tracker-shift-projection): Tracker shift projection and object-class config in Tracker Evaluation, merged to `main` (#1979).
2. [PR 2](#pr-2-multi-camera-geometry-fusion): Multi-camera geometry fusion with time-chunking only, merged to `main` (#2028).
3. [PR 6](#pr-6-tracker-service-3d-detection-input): Tracker Service 3D detection input, merged to `main` (#2050) and into all feature branches.
4. [PR 3](#pr-3-imm-ukf): IMM-UKF fixes, merged to `main` (#2036, `3f0814c6f`) with three follow-ups; tuning items moved to PR 8.

## Tasks In progress

1. [PR 4](#pr-4-mahalanobis-association): Mahalanobis association (#2037); scenario tests, the test broken by the PR 3 merge and the Copilot review threads done; coverage, evaluation, config fixes and filter settings in the service configs open.
2. [PR 5](#pr-5-non-planar-z-tracking): Non-planar Z / `vz` tracking (#2109); port done, conditional z gating, `vz` noise and evaluation open.
3. [PR 7](#pr-7-per-detection-measurement-noise-r): Per-detection measurement noise R (#2129); consumption done, producer and opt-in switch open.

## Tasks Not started

1. [PR 8](#pr-8-dataset-and-testing): Tuning items from PR 3, final accuracy and performance evaluation of the stack, then merge to `main`.
2. [Parallel 1](#parallel-1-dataset-with-diverse-motion): Tracker Evaluation dataset with more diverse motion (cars).

## Details

### Context

| PR  | Branch                                        | Base                                          | GitHub        |
| --- | --------------------------------------------- | --------------------------------------------- | ------------- |
| 1   | `tracker-eval-projection-shift`               | `main`                                        | #1979, merged |
| 2   | `multi-camera-geometry-fusion`                | `main`                                        | #2028, merged |
| 3   | `feature/prob-tracking-extracted` (deleted)   | `main`                                        | #2036, merged |
| 4   | `feature/prob-tracking-extracted-association` | `main`                                        | #2037, open   |
| 5   | `feature/prob-tracking-extracted-3d`          | `feature/prob-tracking-extracted-association` | #2109, open   |
| 6   | `ITEP-97104_tracker_3d_detections`            | `main`                                        | #2050, merged |
| 7   | `feature/prob-tracking-extracted-3d-R`        | `feature/prob-tracking-extracted-3d`          | #2129, open   |
| 8   | –                                             | `feature/prob-tracking-extracted-3d`          | –             |

- Each feature branch merges its base after every upstream change; PR 4 merges `main`, its base since `feature/prob-tracking-extracted` was deleted after #2036.
- Streaming (Controller Immediate mode) fusion was removed from PR 2 (#2061): the Controller is to be deprecated and the Tracker Service uses time-chunking only.

### Tasks Done

#### PR 1: Tracker shift projection

- #1979 (`40fce5198`): Tracker Service object class and shift projection (without the new association config); Tracker Evaluation accepts the object-class config; docs and impact evaluation.
- Unrelated fixes carried along: `CONTRIBUTING.md` license link, `mlops-integration-reuse.md` links, evaluation README / `Agents.md` config names, whitespace.

#### PR 2: Multi-camera geometry fusion

- #2028 (`feaf1d6d5`): time-chunked geometry fusion, birth clustering with the configured `distanceThreshold`, unequal birth-clustering weights fixed, robot-vision UT in CI, `fuseGeometry` coverage, impact evaluated; reached PR 3 in `703566358`.
- Streaming fusion removed before the merge (#2061, [discussion](https://github.com/open-edge-platform/scenescape/pull/2028#discussion_r4232521428)): it added a second smoothing layer on top of the Kalman filter. Impact on Controller Immediate (Unity): HOTA +0.002, DIST_T −5 mm, rms_jerk +154 %, acceleration_variance +390 %; Wildtrack within noise except IDF1 −0.014; time-chunking and Tracker Service within noise. Jitter follow-up: PR 8.
- Multi-camera benchmark scenarios from `tdorau/tmp-rv-benchmark-multicamera` were ported to PR 4 (`e1292f438`).

#### PR 6: Tracker Service 3D detection input

- #2050 (`be9a92bb7`): detection `translation` / `size` / `rotation` and detections without a pixel bounding box; replaces the Tracker input changes of `feat/tracking-z-axis`.
- Merged into PR 3 (`d8646063b`), #2056 (`181a851d4`), PR 4 (`1fd627aa2`) and PR 5 (`d20bb3775`); PR 5 follow-up: `zMeasured` on the translation path (z review Z5, E5).

#### PR 3: IMM-UKF

Merged to `main` as `3f0814c6f` (#2036, squash). Carried over: IMM `S_pred` and mixing fixes, process-noise and initial-covariance redesign (`MultiModelKalmanEstimator.cpp`), UKF fixes (`UnscentedKalmanFilter.cpp`). Test-level history: [PR 3 test plan](../deprecated/prob-tracking-pr3-rv-tests-plan.md) (deprecated).

Done:

- Per-model process noise, including turn rate (F-1, #2056; yaw review E3, delta 9.8): CTRV wins car turns (μ 0.18 → 0.57) and learns the turn rate (0 → 0.38 rad/s); Unity HOTA +0.004, DIST_T −5 to −7 mm; `track()` +1.6 %.
- Per-model predicted measurements (F-3, #2056; yaw review E2): fixed-size `cv::Matx` in `TrackedObject`, move-only estimator, unused `getTrack()` / `getKalmanEstimator()` removed.
- Test split, scenario tools and coverage (#2048): production {CV, CA, CTRV}, manoeuvres, stops, circles, rectangular path; direct UT for `processNoiseCov`, initial covariance caps and re-initialisation (prob review G8, G14).
- Scenario recording and visualization (#2086), detections validated against the Tracker 3D schema (#2050).
- Strict C++20 build; CI builds the Controller image when `controller/src/robot_vision/**` changes.
- Kalman filter settings documented (`4ac31c2f7`; prob review 4): process noise, measurement noise and initial covariance in the robot_vision README ("Kalman filter settings") and the Python docstrings; made-up tracker config example in `controller/Agents.md` replaced with the real keys. Not in `how-to-configure-tracker.md`: neither service reads them from its config; the how-to follows when they are exposed ([PR 4](#pr-4-mahalanobis-association) open item 7).
- Reduced yaw update for detections without orientation (F-2, `6277c8cf5`; yaw review 2): the yaw row is left out of the UKF update and the model likelihood, instead of a fake measurement at the predicted yaw; ADR 0017 wording fixed. Camera-only turns (10 seeds): position RMS −25 to −47 %, CTRV turn rate 0.38 → 0.42 rad/s in a 0.5 rad/s car circle and 0.03 → 0.24 rad/s in a 0.4 rad/s person turn, final speed after a turn +0.03 to +0.09 m/s; C-12 car and person circles within 0.15 m. LiDAR 1 s after 10 s of camera: 0.33 → 0.49 rad of a 0.5 rad step. `SingleJumpingDetectionTracking` had passed only through the fake yaw; now a known-issue skip.
- Velocity tolerance explained (`1161e771f`; prob review 5): on constant-velocity targets the velocity error is 3–6× main's (300 seeds), because the velocity noise, about 300× main's, makes the filter follow the detections for manoeuvre response. `VELOCITY_TOLERANCE` = 0.05 m/s documented in `tracking_test.py`; the tests are seeded (unseeded they exceeded 0.05 about once in 2000–3000 runs). Restoring 0.01 needs less velocity noise: PR 8.
- Initial velocity variance (F-7, `68f5d696d`; delta 9.2): the 0.05 cap dropped, the velocity starts at `init_state_covariance` (1, as on main). The cap was a regression against main: with the services' 2 m Euclidean gate at 10 fps a car entering at 8 or 10 m/s made 11 or 14 tracks and never became reliable; now one track at 8 m/s, 3.8 at 10 m/s. Position RMS −2 to −19 % at 10 fps, −9 to −55 % at 2 fps. Raising 1 → 16: PR 8.
- Cholesky failure recovery (F-6, `c4393854f`; baseline 9.4): a failed factorisation left a half-factorised matrix with inverted diagonal entries (a variance of 4 became 0.25); a finite covariance is now symmetrized, its eigenvalues raised to a floor, with one warning. Never reached in 2 h standing, 1 h circles at 10 and 1 fps, coasts or the jump runs.
- Sigma-point weights kept at κ = 3 − n (E-1, `a222bd748`; baseline 9.4, delta 9.10): no measurable effect at 10 fps (≤ 0.001 m) or 2 fps (≤ 0.01 m); one CTRV step with a turn-rate uncertainty of 1 rad gives a mean speed of 1.84 m/s against the exact 1.82 (κ = 0: 2.51); baseline's 7.2 m/s no longer reproduces. Documented in code and README; a UT pins it.
- Contiguous measurement rows without copying (F-8, `bd70d616d`): F-2's reduced update copied rows and blocks for every model and detection; contiguous rows are now views. `track()` −4.5 % single-threaded, −4.2 % with 4 threads; outputs bit-identical.
- Double precision only (F-9, `5fb7b1878`; [review comment](https://github.com/open-edge-platform/scenescape/pull/2036#discussion_r4460501876)): F-6's eigenvalue floor is lost in float32 rounding; single-precision filters are rejected (robot_vision creates none) and a repair that cannot be factorised falls back to a diagonal factor; outputs bit-identical.

- Follow-ups by the PR author, merged with #2036. Measured on PR 4 @ `f8c55f4ec` merged with the #2036 head, against PR 4 alone (Release): robot_vision 93 of 94 pass (the new test passes; the failure was fixed in [PR 4](#pr-4-mahalanobis-association), `7b93ad99f`), all 216 scenario recordings bit-identical; PR 4 benchmark +0.2 to +0.6 % per frame (time-chunking 4.85 → 4.87 ms, Immediate with 2 cameras 8.42 → 8.47 ms), near the run-to-run noise, likely the finiteness check on every sigma-point draw.
  - `71da06b5d`: `updateModelProbability` gets the full owning matrices and selects the observed rows itself. A refactor: the commit says F-8's contiguous views dangled, but `rowRange` views share the reference-counted buffer of the `cv::Mat(Matx)` copies, and the previous code runs clean under AddressSanitizer.
  - `a1883e810`: a non-finite P (NaN or Inf) gets a diagonal Cholesky factor, with non-finite and tiny variances at 1e-9, instead of the half-factorised matrix; extends F-6 / F-9 + UT `PredictRecoversFromNonFiniteCovariance`. It does not repair a non-finite state: a NaN detection starts a track of its own whose P is NaN again after every predict, before and after the change (never reliable, dropped after `max_unreliable_time_s`; the existing track coasts and keeps its id); see PR 8.
  - `d3f3a520e`: for detections without orientation the legacy `DistanceType::Mahalanobis` cost uses the inverse of S without the yaw row and column (yaw marginalised) instead of zeroing ν_yaw against the full S⁻¹, consistent with the reduced update and the model likelihood (baseline 9.9, in part). Zeroing overstated the distance when S couples yaw and position. Used only by `Mahalanobis` and `MCEMahalanobis`, which neither service selects, but it inverts a 6×6 matrix (SVD) per track–detection pair: `match()` with 50 tracks × 50 detections goes from 0.08 to 4.7 ms; see PR 4 open item 8.

Won't fix:

- Rank orienting yaw by the detected-class probability ([F-4](../deprecated/prob-tracking-pr3-rv-tests-plan.md#f-4-rank-orienting-yaw-by-class-probability); yaw review 6): the Tracker service never sets `classification`, so `applyOrientingYaw` ranks by camera order there. Only the Controller (to be deprecated) builds `[c, 1−c]`, which misranks only when two orienting detections of one track arrive in one chunk and one has c < 0.5.
- Velocity noise direction for standing tracks (delta 9.9; [review comment](https://github.com/open-edge-platform/scenescape/pull/2036#discussion_r4248893254)): a standing car's gate is 0.495 × 0.485 m (ratio 1.02, 1.06 after a 1 s coast), the world-x fallback below 1 mm/s is not reached (the noisy speed stays near 0.03 m/s) and PR 3 associates with a Euclidean gate. Matters only with more standing-track velocity noise: see [PR 8](#pr-8-dataset-and-testing), velocity noise of standing tracks.

Open: None

### Tasks In progress

#### PR 4: Mahalanobis association

Carried over: Mahalanobis association (`ObjectMatching.cpp`), association config pass-down and association window in the Controller and Tracker Service, Tracker Evaluation configs, Manager UI window, docs, benchmark fix, fixed birth-clustering radius.

Done:

- Tracker-level association scenarios (`bf8aee1d4`): `TrackerRun` drives `MultipleObjectTracker`, each scenario runs and records both methods. Only Mahalanobis keeps a car braking while occluded and a person appearing 1.8 m beside an occluded one; exact crossings swap identities with both. Known issues (skipped): `CarEnteringAtSpeedGetsOneTrack`, `CarPullingAwayKeepsOneTrack`; `RunnerEnteringGetsOneTrack` passes since the PR 3 merge `cbd0ca6d9` (`68f5d696d`).
- Car passing a walking person (`70ed421d9`): both methods keep both tracks. A sweep of car + person scenarios (overtaking, oncoming, crossing at 90° and 45°; 5–15 m/s; 1.0–2.5 m apart; either object occluded) found no other case that separates the methods.
- Tracker Evaluation forwards the association config to the Tracker Service (`c7ca00d84`) + harness test.
- Updated with PR 3: streaming fusion removal, C++20, test split (#2103; z review E3) and #2056 (`cv::Matx` access, `getTrack()` removal, benchmark Kalman matrices: `e1292f438`, `671601473`; z review I1).
- Multi-camera benchmark scenarios (`e1292f438`; prob review 21), keeping `--association-config`.
- Visualization wording: with `position_mahalanobis` the 99 % `S_xy` ellipse is the gate up to `max_radius_m`; zoom videos draw the recorded method's gate.
- `scene_pytest` robot_vision mocks scoped to each module (`0a443c757`; z review E4): the 5 association tests pass in full-suite runs.
- Cognitive Complexity check fixed (`3b4b0555f`): `add_association_window` in `scene_common.association` copies the optional `association_window` for `serialize_for_event` and `prepareObjDict`, back at their baseline; passthrough tests in both.
- Unused `kTrackingDistanceThreshold` removed from `tracking_worker.cpp` (`67a14e020`); the load test README and `simulate-detections.js` refer to `tracking.association` instead.
- Per-method `max_radius_m` default (`aa4e6905e`): without it `euclidean` uses the legacy 2 m gate and `position_mahalanobis` the 10 m ceiling, in both services; the Tracker resolves it after the env overrides, using the formerly unused `kDefaultAssociationMaxRadiusM` (prob review 16); how-to and config schema updated.
- Benchmark default association (`7d41f3a99`): without `--association-config` the production association (`position_mahalanobis`, 0.99, 10 m) instead of the tracker's built-in `MultiClassEuclidean` 5 m path; config files get the service defaults for missing keys; stale buffer-aliasing comment dropped.
- Benchmark tracks with the production filter and lifecycle settings (`37be27721`): with the former default config (r = 0.01) the Mahalanobis gate fragmented tracks in the overlapping 2-camera layouts, 1.3–1.7 births per frame instead of 0.5; now 0.5 everywhere.
- `PositionMahalanobisPrefersAlongTrackAxis` fixed (`7b93ad99f`), unblocking CI `make -C tracker test-robot-vision`: the C++ and Python tests called `setMeasurement` before `predict()`, which drops pending measurements, so the track only coasted.
- Copilot review threads of #2037 (prob review 7, 18, 20, 22, 24; open item 11), one commit each:
  - Non-finite association values (issue 20): the Controller's `max_radius_m` `"nan"` / `"inf"` falls back to the method default (`e705313e2`); the Tracker's `TRACKER_ASSOCIATION_GATE_PROBABILITY` / `_MAX_RADIUS_M` `nan` / `inf` fail startup (`94ac84239`); how-to updated.
  - Benchmark `RV_HAS_*` guards, the `ObjectMatching.hpp` grep and the README legacy-tree note dropped (issue 18, `f4c717d4a`).
  - `compare.py` dependencies hash-pinned (issue 24, `6a4f75bd5`): `requirements-compare.txt` with numpy 2.4.1 / scipy 1.17.0, the v1.9.5 tag's versions, as Linux x86_64 / aarch64 wheels for CPython 3.11–3.14; the unpinned pip / setuptools / wheel upgrade dropped; copyright year.
  - Default 2D `.association-window` stroke `#33cc66`, the 3D view's colour (issue 22, `74fccb8e2`).
  - `render_video.py` clamps `gate_probability` to [1e-9, 1 − 1e-9] as `rv::chi2Threshold` does (open item 11, `e0635a970`).
  - `data_formats.md` and the `scene-data` schema say the window is drawn at the corrected `translation`, not the predicted position the gate uses (issue 7, `5022ed7c6`).
- Entering-target tests (open item 2, `0d48d3c09`): `RunnerEnteringGetsOneTrack` is a regression scenario (Mahalanobis keeps entries up to 6 m/s at 10 fps; 8 m/s fails 2 of 3 seeds); `CarEnteringAtSpeedGetsOneTrack` and `CarPullingAwayKeepsOneTrack` stay known issues for [PR 8](#pr-8-dataset-and-testing), their comments updated.
- Coverage (open item 3; prob review G4, G6, G7, G12, G13, G15); each new test fails on a mutated implementation:
  - `PositionMahalanobisPrefersAlongTrackAxis` (C++ and Python) asserts through `match()`: in a wide gate the along-track detection wins, at χ²(0.99) only it is inside the gate (G7, `4a4c26826`).
  - `max_radius_m` rejects a pair inside the χ² gate, 0 rejects any offset, ∞ is the default; the same on the Euclidean branch (G4, `4eaece944`).
  - A degenerate `S_xy` (`|det| < 1e-12`: zero, rank one, 1e-14) is never assigned; det 1e-10 is (G6, `b907d869a`). PR 5's 3×3 path must keep it (PR 5 open item 7).
  - The Controller's `update_tracks()` and `update_tracks_batched()` forward distance type, threshold and `max_radius_m` to `track()` (G12, `a7b5e3944`).
  - Tracker `buildAssociationWindow` UT: circle, rotated `S_xy` (axes, order, angle mod π), negative-eigenvalue clamp (G13, `5c33d37a9`); the safety net for open item 6.
  - Benchmark (G15): Mahalanobis against Euclidean per `track()` call −1.7 to +6.1 %, median +1.8 % (12 cases: time-chunking and Immediate, 50 / 200 people, 1–2 cameras; one pinned thread, median of 7, CV ≤ 2 %), e.g. time-chunking with 200 people 31.5 → 32.3 ms; part of it is different association outcomes, not the 2×2 inverse. The baseline for PR 7's per-pair S.
- Association window cost (open item 6; prob review 14): the Tracker's `cv::eigen` takes 0.47 µs per window (0.3 % of a 200-object frame, 0.1 % of a core at 2000 windows per second), left as is. The Controller's `build_association_window` takes 5.3 → 0.94 µs with a closed-form 2×2 (`064df2573`; 200 objects 1.06 → 0.19 ms per frame) and falls back to the circle for a non-finite S instead of publishing NaN axes; Python twins of the G13 tests first (`5531dbf2d`); `angle_rad` documented as defined modulo π.
- Flaky Tracker unit tests (found while testing PR 4; `057d04cf7`): `TelemetryTest.MultipleRecordingsAccumulate` and `MetricsTest.ConcurrentRecording` / `MultipleCounterIncrements` failed in full-suite runs under load (5–7 of 15; 61 of 150 for the two suites). The SDK's in-memory store keeps the first exported point per series and the periodic reader exports once as soon as its thread starts, so an export between two recordings froze a partial value. The tests use cumulative temporality and a store that answers from the latest export (`utils/in_memory_metrics.hpp`); 0 of 300 and 0 of 15 fail under the same load.

Open:

4. Evaluate on Unity and Wildtrack, `position_mahalanobis` against `euclidean` ([Context](#context)): the baseline for PR 5 and for every noise change. Replace the stale Phase 1 notes in `.github/plans/plan-probabilistic-tracking.md` (prob review 25): they cite artefacts under `/tmp/phase1-*` that are gone, and accept Wildtrack IDSW +23 (over the +5 % budget) and Controller time-chunking rms_jerk +17 % (over +10 %) for Phase 1.

<!-- Open item 5 moved to PR 8 and 6 is done, see Done; the numbers stay stable. -->

7. Expose the filter settings and the birth-clustering radius in both services, global and read at startup, as the design doc's `filter` block (§5.5) next to `association`: Controller `tracker-config*.json`, Tracker `tracking.filter` and `tracking.association` with schema and env overrides (`TRACKER_FILTER_*`, `TRACKER_ASSOCIATION_BIRTH_CLUSTER_RADIUS_M`). Neither service, nor `main`, reads the filter settings from a config today.
   - `filter.process_noise` (q, `kProductionProcessNoise` 1e-4): scales all process noise: velocity density q·1000·(1 + speed) along the track and 1 % of q·1000 across, the same for CA acceleration, CTRV turn-rate density q·1000, yaw q·0.01; no position or size noise. One value moves all of them; PR 8 may split it ([tuning guide: separate noise roles](prob-tracking-imm-tuning.md#separate-noise-roles)).
   - `filter.base_measurement_noise` (r, `kProductionMeasurementNoise` 0.2): detection noise R of every measured component and the initial variance of the measured states; with PR 7 it becomes the default for detections without their own R.
   - `filter.init_state_covariance` (P0, `kProductionInitStateCovariance` 1): since F-7 the initial velocity variance; it also caps the initial acceleration (0.1), yaw (0.05) and yaw-rate (0.01) variances, so values below 0.1 lower them. PR 8's 1 → 16 step uses it.
   - `association.birth_cluster_radius_m` (`kDefaultBirthClusterRadiusM` 2 m, a constant today): clusters detections of one new object from different cameras with a Euclidean distance, because raw detections have no `S_pred`; kept apart from `max_radius_m` so a 10 m ceiling does not merge births in dense scenes. PR 5's `EuclideanBirth` (XYZ when both detections have measured z) uses the same radius.
   - Defaults from the robot_vision production constants (`kProduction*`, Python `PRODUCTION_*`), so both services share one default. Validation: finite values only, as for the association block (`e705313e2`, `94ac84239`); q, r and P0 > 0, the radius ≥ 0. Per-category q (target dynamics) waits for PR 8; per-detection r comes with PR 7.
   - UT: parsing, env overrides and forwarding into `TrackManagerConfig` / `track()` in both services. Docs: a `how-to-configure-tracker.md` section with the meaning above (closes the how-to part of prob review 4) and a note that every filter change also moves the association gate; design doc §5.5. Add the blocks to the Tracker Evaluation black-box configs, so PR 8 sweeps change configs only.
   - Not exposed: `motion_models` (the IMM transition matrix and probability floor depend on the model count, and model subsets did not fix the turn offset), the process-noise shape factors and the IMM prior (PR 8 redesigns them, [tuning guide](prob-tracking-imm-tuning.md#separate-noise-roles)), UKF α / β / κ (E-1), the initial-covariance caps, numerical guards, the score threshold (the low-score stage never triggers, PR 8) and the yaw gate thresholds (item 10).
8. Wrap the yaw difference in the legacy `DistanceType::Mahalanobis` cost (`calculateMahalanobisDistance`, `ObjectMatching.cpp`; yaw review 3): the detection yaw is in (−π, π], the predicted yaw is unwrapped and can be off by π after the direction-of-travel flip, so the innovation can be near π or 2π, block the match and split the track. Use `-rv::deltaTheta(measurement.yaw, predictedYaw)`, which is π-aware, and apply the `prepareYawMeasurement` speed gate (at 1 m/s or more the yaw is flipped by π toward the direction of travel and dropped if still more than 0.6 rad off), so yaw that the update drops does not gate either. Latent: neither service uses `Mahalanobis`. The legacy cost is also not χ²-calibrated (baseline 9.9): it returns ½·√d², so its threshold is no χ² confidence; calibrate it or document it as legacy (the yaw row is marginalised since `d3f3a520e`). Cache the inverse of S without yaw per track, as `PositionMahalanobis` caches its 2×2 inverse: `d3f3a520e` inverts it per track–detection pair (50 × 50 `match()` 0.08 → 4.7 ms). UT: ±π wrap and the speed gate.
9. Assign or defer the open prob review issues; "decided" marks the ones with a chosen fix (several raised again by the Copilot review of #2037):
   - 1: the how-to's "Rollback to Euclidean" restores only the gate: PR 3's filter changes (IMM mixing, process noise, UKF fixes) stay, so `euclidean` does not reproduce `main`; say so in `how-to-configure-tracker.md`.
   - 9: the services handle an invalid `method` differently, and the how-to ("Invalid `method` values fail startup (Controller raises; Tracker throws)") describes neither: the Controller's `extractTrackerConfigData` logs, drops the method and continues with the default (its test asserts the fallback); the Tracker throws. Align them and fix the how-to.
   - 19: with an invalid `method` the Controller keeps the other fields of the block (a test asserts that `max_radius_m` 7.0 survives `method: 'bogus'`); a malformed block should fall back to all defaults. Decide with 9.
   - 12: d² is unbounded and can exceed the matcher's `kDefaultClassBoundValue` (1000): 9 m from a track with S ≈ 0.04 m² gives about 2000. Probably benign, since pairs are compared against the χ² threshold, but untested; clamp with `std::min(d², kDefaultClassBoundValue)` + UT.
   - 13: `normalize_association_config()` runs on every `association_match_params()` call (per frame) and every `build_association_window()` call (per object per frame); with `position_mahalanobis` and `max_radius_m` ≤ 2 m its warning is logged per object per frame, and `_warn_deprecated_tracking_radius` warns every frame. Normalise once at construction and warn once.
   - 15: `MultipleObjectTracker::mMaxRadiusM` is never assigned (always ∞) but the convenience `track(objects, timestamp, scoreThreshold)` overloads pass it, so a tracker built with `PositionMahalanobis` and called through them has no ceiling. Set it in the constructor or stop using it.
   - 16: remaining dead code: `calculatePositionMahalanobisSquaredDistance` (`ObjectMatching.cpp`, a copy of the cached path that PR 5 extends to 3×3; z review Z7), the Python aliases `DEFAULT_ASSOCIATION_MAX_RADIUS_M` / `RECOMMENDED_MAHALANOBIS_MAX_RADIUS_M` (`ilabs_tracking.py`), and `TimeChunkedIntelLabsTracking.applyAssociationConfig`, which only calls `super()`.
   - 22 (decided): per-category colours in the 3D view, which uses one colour (`0x33cc66`) for all; the 2D default stroke is done.
   - 23: switching the UI toggle on shows nothing until the next MQTT message, because `updateAssociationWindow` (2D `marks.js`, 3D `assetmanager.js`) creates geometry only while the toggle is on; redraw from the last message.
   - 26: `association_window` (MQTT contract and UI) is missing from ADR-0017 and the design doc; add it, with the note that it is drawn at the corrected position, not the predicted one the gate uses (issue 7, done in `data_formats.md`). The `.github/plans` file touch list, which puts `MultiModelKalmanEstimator.*` in Phase 3 only, goes with item 4.
   - Benchmark hygiene: 10 (decided): pin google/benchmark by commit in `FetchContent` and in the `compare_benchmarks.sh` clone, and `requirements-compare.txt` with it. 17: `--association-config` is parsed by about 70 lines of string scanning (`jsonStringField`, `jsonNumberField`) that mis-parse nested objects, escaped quotes or a key inside a comment; use a JSON parser (RapidJSON is in the Tracker's conan build, not in robot_vision) or document the flat format.
10. Hysteresis on the yaw publish switch + UT in both services (yaw review 4; moved from PR 3, where it was "yaw thresholding when unreliable"): the Controller's `_kalman_yaw_disagrees_with_velocity` and the Tracker's `select_track_rotation` use single cutoffs (1 m/s, 0.6 rad), so the published rotation can jump by 0.6 rad or more near either. Reuse `SPEED_THRESHOLD_ON` / `OFF` (1.0 / 0.5 m/s) and add an angle off-threshold, chosen now that F-2 changed how far Kalman yaw lags the heading. Also decide whether the fallback may publish the direction of travel where `rotation_from_velocity` is disabled; it does today, undocumented. The thresholds are defined twice and are not configurable (yaw review 7): robot_vision `MIN_SPEED_FOR_YAW_GATE` / `MAX_YAW_VELOCITY_RESIDUAL` (`OrientationAttributes.hpp`, also used by the Tracker) and the Controller's `SPEED_THRESHOLD_ON` (`moving_object.py`) / `YAW_VELOCITY_DISAGREE_RAD` (`ilabs_tracking.py`); expose the robot_vision values to Python or pin them with a test. UT: switch near both thresholds, and `rotation_from_velocity` off on a track that has seen orientation.

<!-- Open item 11 is done, see Done; the numbers stay stable. -->

12. ADR-0017 gaps (yaw review 5 and its ADR notes): it does not say that a vehicle reversing at 1 m/s or more is shown facing the wrong way (the yaw gate and the publish logic put the front along the direction of travel), that CTRV integrates yaw with the turn rate (introduced by the yaw fusion, #1958, but described as existing behaviour), or how the Tracker Service publishes rotation (identity unless orientation was observed, #2050).

#### PR 5: Non-planar Z tracking

Carried over from `feat/tracking-z-axis`: `vz` in a 13-state UKF with named `StateIndex` / `MeasurementIndex`; XYZ Euclidean and 3×3 `PositionMahalanobis` (χ² df 3, UI window df 2); hybrid `EuclideanBirth`; `vz` published by both services; unit tests and `test_z_tracking.py`. Its Tracker 3D input was replaced by PR 6.

Done:

- 13-state filter tests, `constexpr StateSize` checked against `StateIndex`, `std::numbers::pi`, cached χ²(3) threshold (z review E2, I2, Z7).
- Updated with PR 4 including #2050 (`d20bb3775`); `zMeasured` on the Tracker translation path + `TrackingWorker` tests (`9b2879806`); Tracker z-tracking docs (`d0ce0a7d9`) (z review E5).
- Merged #2056 (`270b72b7f`): `StateSize = 13` kept, `processNoiseCov` on `StateIndex` with `Q(vz) = q_vel·dt` (z review I2).
- Association scenarios with the services' χ²(p, 3) gate (`f00f03023`; Copilot review of #2109): one scenario red until item 1.

Open:

1. Conditional z gating + mixed-source UT (z review Z1, Z2). Planar detections report the ground point (z = 0), 3D detections the detector's reference point (usually the box centre), and association gates Δz for every pair; only birth clustering (`EuclideanBirth`) checks `zMeasured`. With production settings a 3 s planar track has S_zz ≈ 0.25 m²: at the same XY, Δz = 0.9 m uses 29 % of the χ²(3) budget, 1.5 m 80 %, and from about 1.7 m the detection is rejected and the track splits. In the Tracker's batched path (pixel camera at z = 0, 3D sensor at box-centre height c): both sensors in every chunk give one track at height c/2; 2 s camera then 3D splits at c = 2 m; alternating sensors give spurious `vz` up to 0.16 m/s. Planar-only scenes get χ²(3) = 11.34 instead of 9.21, 11 % wider in σ: at that gate `PersonAppearingBesideOccludedPersonGetsOwnTrack` fails (identity errors 2 4 4 per seed, 0 at df 2), as the coasting track takes the detections 1.8 m beside it; it stays failing until this fix. Fix: gate z only when the detection has `zMeasured` and the track has been updated with measured z (a sticky flag, like `orientation_observed`), with df 2 otherwise (per pair); agree on one z reference (ground contact or centre) and convert at ingest; `TrackerRun::positionMahalanobisAssociation` (robot_vision tests) follows the per-pair df. #2050's `Tracking_Mixed2DAnd3DMeasurementsPublishSingleTrackWith3DYaw` puts both detections at z ≈ 0, so it does not cover this.
2. Draw the association window with the df used for matching (z review Z3): it uses χ²(p, 2) on the XY block, but the XY footprint of a 3-DOF gate is that block with χ²(p, 3), about 11 % larger; after item 1 the df depends on the pair, so draw with the track's df.
3. `vz` process noise (z review Z4): `Q(vz) = q_vel·dt` adds 0.01 (m/s)² per 0.1 s, as much as horizontal velocity. Noisy depth (stereo, LiDAR) gives spurious `vz` and z drift in coasts, and since `isDynamic` uses the 3D speed, the noise can switch a track between the static and dynamic coast timeouts. Give `vz` its own smaller per-model noise, or pin `vz` = 0 for ground-bound categories + noisy-z coast UT.
4. Docs still describe a 2×2 / 2-DOF gate (z review Z9): `how-to-configure-tracker.md` (`gate_probability`: "2 DOF"), the design doc, ADR-0017 and the `association_window` description in `data_formats.md`; the Z section of `.github/plans/plan-probabilistic-tracking.md` still cites `feat/tracking-z-axis` hashes. Also document that the Controller sets `zMeasured = 'translation' in info`, which is true for child-scene and external-source objects whose z is a planar ground point, so birth clustering uses XYZ for them (z review Z6; benign today).
5. Coverage (z review Z10): the new filter tests use a single CV model; add production IMM {CV, CA, CTRV} with vertical motion, mixed planar / 3D association (item 1), a noisy-z coast (item 3) and the window df (item 2). Run the functional `tests/functional/test_z_tracking.py` (needs the container stack; never run).
6. Evaluate on Wildtrack and Unity against PR 4 (z review Z2); after item 1, planar scenes must match PR 4.
7. Restore a near-singular guard in the 3×3 `PositionMahalanobis` paths (z review Z7): PR 5 replaced `|det S| < 1e-12` with `cv::invert(S, Sinv, cv::DECOMP_LU) == 0` (`ObjectMatching.cpp`), which only catches an exactly singular S; check the determinant or the condition number + UT with a near-singular S; PR 4's `PositionMahalanobisNeverAssignsTrackWithDegenerateCovariance` pins the 2×2 behaviour.

#### PR 7: Per-detection measurement noise R

`robot_vision` side of Phases 2 and 3 in [ADR-0017](../../adr/0017-probabilistic-tracking-association.md), ported from `feat/full-v2-tracking-pipeline-R-aware` (`b1ba13b4a`) in `c116858ee`: optional 7×7 R on `TrackedObject` (Python `measurement_noise_covariance`); per-pair S = H P Hᵀ + R in both Mahalanobis gates; UKF / IMM update and birth P from R; inverse-covariance `fuseGeometry` weights. Without R, scenario recordings are byte-identical to the base. Not ported: Controller observation Σ → R, streaming fusion R fix.

Done:

- A correct without R after one with R, before the next predict, no longer reuses the earlier R + UT.
- [Visualization plan](../deprecated/prob-tracking-viz-plan.md): with R the `S_xy` ellipse is not the gate for that detection.
- Scenario test support (`d2039588f`): `Sensor::positionCovariance` draws the error from a covariance (`groundPlaneCamera`, `depthCamera`, `fixedCovariance`) and reports it as R; the recorder writes R per detection and `HPHt` per step.

Open:

1. Decide and wire the R producer on `main` + UT. Option A, Tracker `CoordinateTransformer` ([design](../../design/probabilistic-tracking-association.md) §5.3): σ_px = max(min_pixel_sigma, α · bbox height in px · f(confidence)), Σ_xy = J Σ_pixel Jᵀ with J the 2×2 Jacobian of the pixel-to-ground projection, optionally scaled by the incidence angle; α calibrated offline (maximise AssA with LocA at least the baseline); settings under `measurement_uncertainty.*`. Option B, the Controller observation pipeline (7×7 frustum Σ, as on `feat/full-v2-tracking-pipeline-R-aware`).
2. Decide the switch: the design adds an opt-in `position_mahalanobis_combined` (S = S_pred + R_meas, Phase 1 behaviour for detections without R) and flips the default in Phase 3 after evaluation (§5.3, §8); this branch uses R whenever a detection carries it. Update design §5.3, §5.4 (`correct(measurement, R_optional)`), §8 and the ADR-0017 Phase 2 / 3 status (both still "proposed").
3. Apply PR 5's z gating (PR 5 open item 1: measured z on both sides, χ² df per pair) to the per-pair R gate (z review Z1, Z2).
4. Combine with PR 3's reduced yaw update for detections without orientation (`6277c8cf5`; yaw review 2): both change the UKF correct, so the per-pair R must apply to the observed rows only.
5. Evaluate impact on Wildtrack and Unity against PR 5 once a producer sets R.
6. Scenario tests with R, as paired runs with and without R: one camera, two cameras at 90°, mixed with and without R, wrong `reportedScale`. In a trial with two ground-plane cameras, R lowered the position error on 19 of 20 seeds.
7. Investigate the track restarts in that trial: at 0.005 rad with R and `position_mahalanobis`, tracks restarted through the whole run (about 2-3 per run); without R or with `euclidean`, extra tracks started only in the first 3 s. Check how the tests generate R and whether it is too small for the gate (0.06 m across the ray at 12 m).
8. Optional: draw the per-detection gate `HPHt + R` in the visualization tools.

### Tasks Not started

#### PR 8: Dataset and testing

- Base `feature/prob-tracking-extracted-3d`: final accuracy and performance evaluation, then merge to `main`.
- Re-measure the [pinned test bounds](#pinned-test-bounds) after each tuning change and tighten them.
- _[tuning required]_ Unobserved yaw variance of camera-only tracks keeps growing since F-2 (`6277c8cf5`): a standing car reaches 4 rad² after 1 min and 41 rad² after 10 min (straight driving 0.17, a circle 0.55 rad² after 10 min), driven by CTRV's turn-rate noise. Covariances stay positive definite and the yaw is not published for such tracks. Cap the yaw variance or lower the turn-rate noise of standing tracks.
- _[tuning required]_ Initial velocity variance 1 → 16 m²/s² (rest of [F-7](../deprecated/prob-tracking-pr3-rv-tests-plan.md#f-7-initial-velocity-uncertainty)): entries up to 15 m/s keep one track through the 2 m gate at 10 fps (now up to 10 m/s); a young track's Mahalanobis coast gate gets rounder (along / across 2.7 → 1.5). Evaluate on Unity and Wildtrack with PR 4's entering-target scenarios; at 2 fps a new track's first gate is about 6 m. Un-skip PR 4's `CarEnteringAtSpeedGetsOneTrack` (10 m/s; passes with both methods at 16) and add a differentiating entering scenario: at 1 Mahalanobis is no better than Euclidean for entries of 4–15 m/s at 2 or 10 fps, so none exists yet. Sweep 0.05 / 1 / 4 / 16 / 64 m²/s² (PR 4 association scenarios with a temporary override, 10 seeds): fastest entry kept at 10 fps with Mahalanobis 3 / 6 / 10 / 15 / 25 m/s, Euclidean stops at 15 m/s (its 2 m gate limits the first frame); from 16 Mahalanobis also keeps 10 m/s at 2 fps; C-9 speed 1 s after a 10 m/s entry 4.98 / 9.06 / 9.78 / 9.94 / 9.98 m/s; side-by-side, standing-pair and crossing scenarios unchanged. Re-pin C-5 (velocity variance `init_state_covariance`); in the sweep only C-5 and `PositionMahalanobisPrefersAlongTrackAxis` failed at 4 and 16; the latter passes for 0.05–64 since [PR 4](#pr-4-mahalanobis-association) `7b93ad99f`.
- _[tuning required]_ Process-noise floor on size ([F-5](../deprecated/prob-tracking-pr3-rv-tests-plan.md#f-5-process-noise-floor); prob review 2, G9; delta 9.1): after 5 min standing a +0.3 m height step reaches 0.7 % in 2 s and 3.2 % in 10 s (main 36 % / 89 %), and the Tracker publishes the filtered size. Covariances stay positive definite (2 h runs); z gets vz noise in PR 5 (z review Z4). Choose the noise, maybe per class; update C-6 and the robot_vision README. Test `LongLivedTrackFollowsSizeChange`: 5 min standing at 10 fps, then a +0.3 m height step; at least 50 % of the step within 2 s, every model covariance positive definite.
- _[tuning required]_ Velocity noise of standing tracks (PR 4 `CarPullingAwayKeepsOneTrack`; delta 9.9): a car accelerating at 5 m/s² from rest gets 16–17 identity errors per seed with Mahalanobis (Euclidean 0). At rest the 100:1 along-track velocity noise points in the noisy direction of the estimated velocity, so the velocity lags the car. Velocity noise qVel · k in every direction, faded out linearly by 1 m/s, fixes it from k = 1 (0.7: 2 of 3 seeds fail; 0.5 fails); in the rest of robot_vision only `ProcessNoisePerModelShape`, which pins the shape, fails. It changes every standing track: evaluate on Unity and Wildtrack, decide with per-category q. A gate floor at the Euclidean radius is rejected: it needs 2 m, and 1.6 m already breaks `PersonAppearingBesideOccludedPersonGetsOwnTrack`.
- _[tuning required]_ Gate covariance of the IMM (PR 4 open item 5; prob review 11, delta 9.4): `predictState` takes the predicted mean from the mixture but S from the most probable model, dropping the spread term Σ μ_j (ẑ_j − ẑ)(ẑ_j − ẑ)ᵀ: the gate can be too tight when the models disagree (turn onset, braking), and with near-uniform μ the chosen model can switch from frame to frame. The best model was chosen because the spread widens the gate in all directions. With the mixture S, PR 4's `PersonAppearingBesideOccludedPersonGetsOwnTrack` fails 1 of 3 seeds (2 identity errors), every other association scenario is unchanged. Decide with the IMM prior and transition tuning ([tuning guide](prob-tracking-imm-tuning.md#transition-probability-per-unit-time)), which sets how μ moves; the same S is published as `measurement_covariance` and drawn as the association window. Also evaluate ln|S| in the cost (delta 9.5): with d² alone a coasting track (large S) can win an ambiguous detection against a well-localised track at the same distance; gate on d², assign on d² + ln|S|; with PR 7 S is per pair.
- _[tuning required]_ Velocity smoothing on constant-velocity targets: 3–6× main's velocity error, the price of the velocity noise for manoeuvres; restoring the 0.01 m/s test tolerance needs less velocity noise ([tuning guide: separate noise roles](prob-tracking-imm-tuning.md#separate-noise-roles)).
- _[tuning required]_ Controller Immediate-mode jitter: find what in the filter gives the reduction streaming fusion gave, without double smoothing. Streaming fusion averaged each detection with the other cameras' cached detections (up to 250 ms old), a second smoothing layer on top of the filter; it was removed from PR 2 (#2061). After F-1 (Unity): Immediate rms_jerk +6 %, acceleration_variance +16 % (noise); time-chunking +39 % / +79 %; Tracker Service −15 % / −22 %.
- _[tuning required]_ Constant offset in sustained turns (known issue): F-2 halved it, the car and person circles are within 0.15 m (a 3 m/s car on a 6 m circle 0.06 m behind, 0.10 m outside); the steady-turn window, dominated by the turn onset, is still 0.09 m behind and 0.15 m outside. Decide with the per-sensor detection noise ([E-2](../deprecated/prob-tracking-pr3-rv-tests-plan.md#e-2-constant-offset-in-sustained-turns); [tuning guide: measure the detection noise](prob-tracking-imm-tuning.md#measure-the-detection-noise)). Mechanism (measured before F-2, `d673ef83a`): under r = 0.2 CTRV holds about half of μ in a circle (CV / CA / CTRV .25 / .27 / .48), and mixing with CV and CA dilutes its turn rate (0.30 for 0.5 rad/s); CTRV alone has no offset (≤ 0.07 m). Only r moves it (r = 0.05: −0.09 / −0.18 m; r = 0.0025: −0.02 / −0.04 m, but CA then wins every turn, μ .75); sensor noise does not, and neither do Markov-predicted μ, dropping the floor rescale, CTRV keeping its own w in mixing, or the model sets {CV, CTRV} / {CA, CTRV}. Verification: un-skip C-12 (`SteadyCircleHasNoConstantOffset`, mean along / cross ≤ 0.15 m).
- Known issue `SingleJumpingDetectionTracking` (skipped since F-2, `6277c8cf5`): a 2 m-per-frame jump, a 200-sigma innovation at r = 1e-4, goes into CTRV's turn rate and splits the track. Holding it needs an outlier-robust update ([tuning guide: robustness to jumps](prob-tracking-imm-tuning.md#robustness-to-jumps)); decide or mark won't fix.
- Non-finite detections: the Controller accepts NaN in detection JSON (Python `json`, schema type `number`). A NaN detection starts a track with a NaN state, never reliable and dropped after `max_unreliable_time_s`; the existing track coasts; `a1883e810` does not change this. Reject non-finite detections at ingest in both services (check the Tracker's parsing and projections) + UT, and reword the `a1883e810` warning, which reports a NaN covariance as "not positive definite".
- Python binding default `beta = 1.0` for the estimator (`extensions/tracking.cpp`) against 2.0 in C++ (baseline 9.10): Python code that builds an estimator directly gets other sigma-point weights than the services; align to 2.0 + UT.
- Note (baseline 9.6): the low-score association stage never triggers. `splitByThreshold` scores a detection by `classification.maxCoeff()`, which is at least 0.5 for the Controller's `[c, 1−c]` and 1.0 for the Tracker's default, so every detection is high-score. Decide or mark won't fix before tuning `scoreThreshold`.

##### Pinned test bounds

Calibrated at `8f1c0d9ef` (Release, fixed seed); C-7 re-calibrated after F-1 (`838f28653`), C-7 and C-9 re-measured after F-3 (`c3c8c3f96`) and F-1 (`2804edf78`), C-7 and C-10 to C-12 at `d673ef83a`; all re-measured after F-2 (`6277c8cf5`) and F-7 (`68f5d696d`); unchanged by F-8 and F-9; F-7, C-11 and E-1 measured at `c426403b8`. Format: bound (measured); "After": the change to re-measure after ("PR 8": any tuning change).

| Test                                                          | Bound (measured)                                                                                                                                                                                                                                                                                                              | After    |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| C-7 `TracksMotionCases`, max error / final speed              | constant velocity 0.10 / 0.03 (0.06 / 0.011), acceleration 0.35 / 0.01 (0.29 / 0.006), turn 0.45 / 0.05 (0.37 / 0.019), sudden stop 0.9 / 0.05 (0.75 / 0.038), manoeuvre 0.45 / 0.2 (0.37 / 0.152), car circle 0.50 / 0.25 (0.41 / 0.172), person turn 0.35 / 0.12 (0.25 / 0.090), rectangular path 0.65 / 0.3 (0.49 / 0.229) | PR 8     |
| C-8 `ConstantVelocityConvergence`                             | 0.05 m/s (CV 0.008 / 0.003, three models 0.008 / 0.002; one seed)                                                                                                                                                                                                                                                             | PR 8     |
| C-9 `TargetBornMovingAcquiresSpeed`                           | ≥ 8.5 m/s (9.06; 4.98 before F-7)                                                                                                                                                                                                                                                                                             | PR 8     |
| F-7 `CarEnteringAtSpeedGetsOneReliableTrack`                  | one track, ≥ 40 of 51 frames reliable (one track, 41; 11 tracks before F-7); 8 m/s, 2 m Euclidean gate, 10 fps                                                                                                                                                                                                                | PR 8     |
| C-6 `ProcessNoisePerModelShape`                               | Pinned formula; zero position, z and size noise                                                                                                                                                                                                                                                                               | PR 8     |
| C-5 `InitialCovarianceUsesMeasurementNoiseAndCaps`            | Velocity init_state_covariance; caps 0.1 acceleration, 0.05 yaw, 0.01 yaw rate (exact)                                                                                                                                                                                                                                        | PR 8     |
| C-10 `SteadyMotionHasNoConstantTrailingOffset`                | ≤ 0.15 m (−0.003 / +0.004); the steady turn moves back here once E-2 passes                                                                                                                                                                                                                                                   | E-2      |
| C-11 `DetectionLatencyLeavesConstantTrailingOffset`           | along within ±0.05 of −speed × lag, cross ±0.05, along spread ≤ 0.2 (−0.316 / −0.608 / −1.201 against −0.30 / −0.60 / −1.20; cross ≤ 0.011; spread ≤ 0.106)                                                                                                                                                                   | PR 8     |
| F-1 `ModelSelection`                                          | CV margin ≥ .03 / .05 (.047 / .090); CA μ ≥ .45 (.56 / .62); CTRV μ ≥ .45 / .40 (.56 / .48), margin ≥ .2 / .1 (.34 / .21); turn exit margin ≥ .03 (.066)                                                                                                                                                                      | PR 8     |
| F-1 `TurningTargetLearnsTurnRate`                             | w in [0.3, 0.6] (0.41), [−0.45, −0.15] (−0.24), ±0.05 (−0.003)                                                                                                                                                                                                                                                                | PR 8     |
| F-1 `CoastingAfterTurn`                                       | ≤ 1.8 m (1.17)                                                                                                                                                                                                                                                                                                                | PR 8     |
| F-1 `OrientingSensorFollowsTurningHeading`                    | ≤ 0.2 rad (0.07), model yaw spread ≤ 0.3 (0.15)                                                                                                                                                                                                                                                                               | PR 8     |
| F-1 `OrientingSensorFollowsRotationInPlace`                   | ≥ 0.35 / 0.45 rad (0.42 / 0.50)                                                                                                                                                                                                                                                                                               | PR 8     |
| F-1 `StraightLineMatchesConstantVelocityFilter`               | ratio ≤ 1.1 (1.05 / 1.07 / 1.03; a single seed varies by about 0.2)                                                                                                                                                                                                                                                           | PR 8     |
| E-1 `CtrvPredictionKeepsGaussianMeanUnderTurnRateUncertainty` | 1.82 ± 0.05 m/s (1.839; κ = 0: 2.51)                                                                                                                                                                                                                                                                                          | κ change |
| C-13 `CameraOnlyTurningYawStaysBounded`                       | yaw variance ≤ 0.2 rad² (0.13), model yaw spread ≤ 0.3 rad (0.17)                                                                                                                                                                                                                                                             | PR 8     |

#### Parallel 1: Dataset with diverse motion

- Adopt a Tracker Evaluation dataset with more diverse motion (cars), merged into `main` for the final evaluation.
