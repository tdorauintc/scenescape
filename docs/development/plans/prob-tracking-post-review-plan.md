<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# `feature/prob-tracking` branch split plan

## High level details

- Branch: `feature/prob-tracking` @ `188c40e79`, split into PRs 1–8, so the accuracy and performance impact of each can be evaluated separately.
- PRs: #1979, #2028, #2050 (merged to `main`); #2056 (merged into `feature/prob-tracking-extracted`); #2037, #2109, #2129 (open). Branch stack: [Details / Context](#context-1).
- Status: PRs 1, 2 and 6 done; PRs 3, 4, 5 and 7 in progress; PR 8 not started.

### Context

- "PR N" (also "step N" or "item N" in other documents) is item N of this plan.
- PRs 1, 2 and 6 go to `main`; PRs 3 → 4 → 5 → 7 are stacked feature branches; PR 8 evaluates the stack and merges it to `main`.
- Review findings are cited by the short names in [Related documents](#related-documents), e.g. "prob review G9", "yaw review E2", "z review Z1", "delta 9.1", "baseline 9.4".

### Related documents

- [PR 3 test plan](prob-tracking-pr3-rv-tests-plan.md): robot-vision tests and test-first fixes for PR 3 (C-n, F-n, E-n IDs).
- [Visualization plan](../done/prob-tracking-viz-plan.md): scenario recording, plots and videos of the robot-vision tests (done, #2086).
- [Tuning guide](../future/prob-tracking-imm-tuning.md): IMM-UKF tuning knobs, KPIs and prerequisites (future work).
- [prob review](../reviews/pr-review-probabilistic-tracking.md): review of `feature/prob-tracking` vs `main`; issues "N", coverage gaps "GN".
- [yaw review](../reviews/pr-review-yaw-fusion.md): review of the yaw fusion commit (#1958); findings "N", related issues "EN".
- [z review](../reviews/pr-review-tracking-z-axis.md): review of non-planar Z / `vz` tracking; findings "ZN", "EN", "IN".
- [baseline](../reviews/robot-vision-tracking-algorithms.md): robot-vision tracking algorithms on `main`; Section 9 items "9.N".
- [delta](../reviews/robot-vision-tracking-prob-tracking-delta.md): robot-vision changes in `feature/prob-tracking`; Section 9 items "9.N".
- [ADR-0017](../../adr/0017-probabilistic-tracking-association.md) and [design doc](../../design/probabilistic-tracking-association.md): probabilistic association decisions and phases.

## Tasks Done

1. [PR 1](#pr-1-tracker-shift-projection): Tracker shift projection and object-class config in Tracker Evaluation, merged to `main` (#1979).
2. [PR 2](#pr-2-multi-camera-geometry-fusion): Multi-camera geometry fusion with time-chunking only, merged to `main` (#2028).
3. [PR 6](#pr-6-tracker-service-3d-detection-input): Tracker Service 3D detection input, merged to `main` (#2050) and into all feature branches.

## Tasks In progress

1. [PR 3](#pr-3-imm-ukf): IMM-UKF fixes; per-model noise and predictions done (#2056), yaw, noise floor and UKF robustness open.
2. [PR 4](#pr-4-mahalanobis-association): Mahalanobis association (#2037); scenario tests done, coverage, evaluation and config fixes open.
3. [PR 5](#pr-5-non-planar-z-tracking): Non-planar Z / `vz` tracking (#2109); port done, conditional z gating, `vz` noise and evaluation open.
4. [PR 7](#pr-7-per-detection-measurement-noise-r): Per-detection measurement noise R (#2129); consumption done, producer and opt-in switch open.

## Tasks Not started

1. [PR 8](#pr-8-dataset-and-testing): Final accuracy and performance evaluation of the stack, then merge to `main`.
2. [Parallel 1](#parallel-1-dataset-with-diverse-motion): Tracker Evaluation dataset with more diverse motion (cars).

## Details

### Context

| PR  | Branch                                        | Base                                          | GitHub               |
| --- | --------------------------------------------- | --------------------------------------------- | -------------------- |
| 1   | `tracker-eval-projection-shift`               | `main`                                        | #1979, merged        |
| 2   | `multi-camera-geometry-fusion`                | `main`                                        | #2028, merged        |
| 3   | `feature/prob-tracking-extracted`             | `main`                                        | #2056 merged into it |
| 4   | `feature/prob-tracking-extracted-association` | `feature/prob-tracking-extracted`             | #2037, open          |
| 5   | `feature/prob-tracking-extracted-3d`          | `feature/prob-tracking-extracted-association` | #2109, open          |
| 6   | `ITEP-97104_tracker_3d_detections`            | `main`                                        | #2050, merged        |
| 7   | `feature/prob-tracking-extracted-3d-R`        | `feature/prob-tracking-extracted-3d`          | #2129, open          |
| 8   | –                                             | `feature/prob-tracking-extracted-3d`          | –                    |

- Each feature branch merges its base after every upstream change; `feature/prob-tracking-extracted` merges `main`.
- Streaming (Controller Immediate mode) fusion was removed from PR 2 (#2061): the Controller is to be deprecated and the Tracker Service uses time-chunking only.

### Tasks Done

#### PR 1: Tracker shift projection

- #1979 (`40fce5198`): Tracker Service object class and shift projection (without the new association config); Tracker Evaluation accepts the object-class config; docs and impact evaluation.
- Unrelated fixes carried along: `CONTRIBUTING.md` license link, `mlops-integration-reuse.md` links, evaluation README / `Agents.md` config names, whitespace.

#### PR 2: Multi-camera geometry fusion

- #2028 (`feaf1d6d5`): time-chunked geometry fusion, birth clustering with the configured `distanceThreshold`, unequal birth-clustering weights fixed, robot-vision UT in CI, `fuseGeometry` coverage, impact evaluated; reached PR 3 in `703566358`.
- Streaming fusion removed before the merge (#2061, [discussion](https://github.com/open-edge-platform/scenescape/pull/2028#discussion_r4232521428)): it added a second smoothing layer on top of the Kalman filter. Impact on Controller Immediate (Unity): HOTA +0.002, DIST_T −5 mm, rms_jerk +154 %, acceleration_variance +390 %; Wildtrack within noise except IDF1 −0.014; time-chunking and Tracker Service within noise. Jitter follow-up: PR 3.
- Multi-camera benchmark scenarios from `tdorau/tmp-rv-benchmark-multicamera` were ported to PR 4 (`e1292f438`).

#### PR 6: Tracker Service 3D detection input

- #2050 (`be9a92bb7`): detection `translation` / `size` / `rotation` and detections without a pixel bounding box; replaces the Tracker input changes of `feat/tracking-z-axis`.
- Merged into PR 3 (`d8646063b`), #2056 (`181a851d4`), PR 4 (`1fd627aa2`) and PR 5 (`d20bb3775`); PR 5 follow-up: `zMeasured` on the translation path (z review Z5, E5).

### Tasks In progress

#### PR 3: IMM-UKF

Carried over: IMM `S_pred` and mixing fixes, process-noise and initial-covariance redesign (`MultiModelKalmanEstimator.cpp`), UKF fixes (`UnscentedKalmanFilter.cpp`). Test-level details: [PR 3 test plan](prob-tracking-pr3-rv-tests-plan.md).

Done:

- Per-model process noise, including turn rate (F-1, #2056; yaw review E3, delta 9.8): CTRV wins car turns (μ 0.18 → 0.57) and learns the turn rate (0 → 0.38 rad/s); Unity HOTA +0.004, DIST_T −5 to −7 mm; `track()` +1.6 %.
- Per-model predicted measurements (F-3, #2056; yaw review E2): fixed-size `cv::Matx` in `TrackedObject`, move-only estimator, unused `getTrack()` / `getKalmanEstimator()` removed.
- Test split, scenario tools and coverage (#2048): production {CV, CA, CTRV}, manoeuvres, stops, circles, rectangular path; direct UT for `processNoiseCov`, initial covariance caps and re-initialisation (prob review G8, G14).
- Scenario recording and visualization (#2086), detections validated against the Tracker 3D schema (#2050).
- Strict C++20 build; CI builds the Controller image when `controller/src/robot_vision/**` changes.

Open:

1. No yaw measurement for detections without orientation (reduced update) + camera-only yaw tests; fix the "predict" wording in the selective-yaw ADR ([F-2](prob-tracking-pr3-rv-tests-plan.md#f-2-no-yaw-update-without-orientation); yaw review 2).
2. Yaw thresholding when unreliable + UT (moved from PR 2).
3. Rank orienting yaw in `applyOrientingYaw` by the detected-class probability + UT ([F-4](prob-tracking-pr3-rv-tests-plan.md#f-4-rank-orienting-yaw-by-class-probability); yaw review 6; moved from PR 2).
4. Process-noise floor on position, z and size + long-duration test ([F-5](prob-tracking-pr3-rv-tests-plan.md#f-5-process-noise-floor); prob review 2, G9; delta 9.1).
5. Document `default_process_noise` and `init_state_covariance` semantics in `how-to-configure-tracker.md` (prob review 4).
6. Explain or revert the velocity tolerance loosening (0.01 → 0.05) in `tracking_test.py` (prob review 5).
7. Velocity prior cap (0.05): a 10 m/s target reaches 4.98 m/s 1 s after birth; decide whether to raise it (delta 9.2).
8. Recover from a failed Cholesky factorisation in `getSigmaPoints` + UT ([F-6](prob-tracking-pr3-rv-tests-plan.md#f-6-cholesky-failure-recovery); baseline 9.4).
9. Sigma-point weights κ = 3 − n vs 0 for CTRV under strong nonlinearity: keep and document, or change + UT ([E-1](prob-tracking-pr3-rv-tests-plan.md#e-1-sigma-point-weights); baseline 9.4, delta 9.10).
10. Controller Immediate-mode jitter: find what in the filter gives the reduction streaming fusion gave, without double smoothing. After F-1 (Unity): Immediate rms_jerk +6 %, acceleration_variance +16 % (noise); time-chunking +39 % / +79 %; Tracker Service −15 % / −22 %.
11. Constant offset in sustained turns (known issue): a 3 m/s car runs 0.13 m behind and 0.23 m outside a 6 m circle; decide with the per-sensor detection noise ([E-2](prob-tracking-pr3-rv-tests-plan.md#e-2-constant-offset-in-sustained-turns); [tuning guide](../future/prob-tracking-imm-tuning.md) §5).

#### PR 4: Mahalanobis association

Carried over: Mahalanobis association (`ObjectMatching.cpp`), association config pass-down and association window in the Controller and Tracker Service, Tracker Evaluation configs, Manager UI window, docs, benchmark fix, fixed birth-clustering radius.

Done:

- Tracker-level association scenarios (`bf8aee1d4`): `TrackerRun` drives `MultipleObjectTracker`, each scenario runs and records both methods. Only Mahalanobis keeps a car braking while occluded and a person appearing 1.8 m beside an occluded one; exact crossings swap identities with both. Known issues (skipped): `RunnerEnteringGetsOneTrack`, `CarEnteringAtSpeedGetsOneTrack`, `CarPullingAwayKeepsOneTrack`.
- Updated with PR 3: streaming fusion removal, C++20, test split (#2103; z review E3) and #2056 (`cv::Matx` access, `getTrack()` removal, benchmark Kalman matrices: `e1292f438`, `671601473`; z review I1).
- Multi-camera benchmark scenarios (`e1292f438`; prob review 21), keeping `--association-config`.
- Visualization wording: with `position_mahalanobis` the 99 % `S_xy` ellipse is the gate up to `max_radius_m`; zoom videos draw the recorded method's gate.

Open:

1. Un-skip the entering-target tests once PR 3 raises the initial velocity uncertainty (velocity prior cap), and add a car entering faster than the Euclidean gate as a differentiating scenario. For `CarPullingAwayKeepsOneTrack` decide between more velocity noise for standing tracks (PR 3) and a gate floor at the Euclidean radius.
2. Coverage: `max_radius_m` ceiling, degenerate covariance, gate costs from the implementation, Controller forwarding to `track()`, C++ `buildAssociationWindow`, Euclidean vs Mahalanobis benchmark (prob review G4, G6, G7, G12, G13, G15). Fix `PositionMahalanobisPrefersAlongTrackAxis` (C++ and Python) to predict → setMeasurement → correct.
3. Evaluate impact on Unity and Wildtrack (`position_mahalanobis` vs `euclidean`); replace the stale Phase 1 notes in `.github/plans/plan-probabilistic-tracking.md` (prob review 25). Baseline for PR 5 and noise changes ([tuning guide](../future/prob-tracking-imm-tuning.md) §5 item 10).
4. Evaluate the mixture covariance vs the best model's covariance for matching.
5. Evaluate and mitigate the cost of `numpy.linalg.eigh` / `cv::eigen` in association window publishing.
6. Make the birth-clustering radius `kDefaultBirthClusterRadiusM` configurable.
7. Wrap the yaw difference in the legacy `Mahalanobis` cost and apply the `prepareYawMeasurement` speed gate + ±π wrap UT (yaw review 3).
8. Fix the session-scoped `controller.ilabs_tracking.rv` mock in `scene_pytest/conftest.py` that fails 5 association tests in full-suite runs (z review E4).
9. Fix the Cognitive Complexity check: extract a helper for the optional `association_window` fields in `serialize_for_event` and `prepareObjDict`.
10. Remove the unused `kTrackingDistanceThreshold` from `tracking_worker.cpp` (re-added by merge `1fd627aa2`); update `tracker/test/load/README.md`.
11. `{"method": "euclidean"}` without `max_radius_m` gives a 10 m gate in both services: use a per-method default or document `max_radius_m` as required.
12. The benchmark default without `--association-config` (`MultiClassEuclidean`, 5 m) matches no production setting: default to a preset or document it; drop the stale buffer-aliasing comment.
13. Assign or defer the open [prob review issues](../reviews/pr-review-probabilistic-tracking.md#6-issues--highest-priority-first) 7, 9, 12, 13, 15, 16, 19, 20, 22, 23, 26 and benchmark hygiene 10, 17, 18, 24.

#### PR 5: Non-planar Z tracking

Carried over from `feat/tracking-z-axis`: `vz` in a 13-state UKF with named `StateIndex` / `MeasurementIndex`; XYZ Euclidean and 3×3 `PositionMahalanobis` (χ² df 3, UI window df 2); hybrid `EuclideanBirth`; `vz` published by both services; unit tests and `test_z_tracking.py`. Its Tracker 3D input was replaced by PR 6.

Done:

- 13-state filter tests, `constexpr StateSize` checked against `StateIndex`, `std::numbers::pi`, cached χ²(3) threshold (z review E2, I2, Z7).
- Updated with PR 4 including #2050 (`d20bb3775`); `zMeasured` on the Tracker translation path + `TrackingWorker` tests (`9b2879806`); Tracker z-tracking docs (`d0ce0a7d9`) (z review E5).
- Merged #2056 (`270b72b7f`): `StateSize = 13` kept, `processNoiseCov` on `StateIndex` with `Q(vz) = q_vel·dt` (z review I2).

Open:

1. Gate z only when both the detection and the track have measured z (sticky track flag), χ² df per pair, one z reference point for planar and 3D detections + mixed-source UT (z review Z1, Z2).
2. Draw the association window with the same df as matching (z review Z3).
3. Per-model `vz` process noise below the horizontal one, or `vz` pinned for ground-bound categories + noisy-z coast UT (z review Z4).
4. Docs: 3-DOF gate in `how-to-configure-tracker.md`, design doc, ADR-0017 and `data_formats.md` (z review Z9).
5. Coverage: production IMM with vertical motion, mixed planar / 3D association; run `test_z_tracking.py` (z review Z10).
6. Evaluate impact on Wildtrack and Unity against PR 4 (z review Z2).

#### PR 7: Per-detection measurement noise R

`robot_vision` side of Phases 2 and 3 in [ADR-0017](../../adr/0017-probabilistic-tracking-association.md), ported from `feat/full-v2-tracking-pipeline-R-aware` (`b1ba13b4a`) in `c116858ee`: optional 7×7 R on `TrackedObject` (Python `measurement_noise_covariance`); per-pair S = H P Hᵀ + R in both Mahalanobis gates; UKF / IMM update and birth P from R; inverse-covariance `fuseGeometry` weights. Without R, scenario recordings are byte-identical to the base. Not ported: Controller observation Σ → R, streaming fusion R fix.

Done:

- A correct without R after one with R, before the next predict, no longer reuses the earlier R + UT.
- [Visualization plan](../done/prob-tracking-viz-plan.md): with R the `S_xy` ellipse is not the gate for that detection.

Open:

1. Decide and wire the R producer on `main`: Tracker `CoordinateTransformer` (2×2 xy from the pixel Jacobian, [design](../../design/probabilistic-tracking-association.md) §5.3) or Controller observation pipeline (7×7 frustum Σ) + UT.
2. Decide the switch: opt-in `position_mahalanobis_combined` (design) or whenever a detection carries R (this branch); update design §5.3, §5.4, §8 and ADR-0017 Phase 2 / 3 status.
3. Apply PR 5's z gating (measured z on both sides, χ² df per pair) to the per-pair R gate (z review Z1, Z2).
4. Combine with PR 3's reduced yaw update for detections without orientation (yaw review 2): both change the UKF correct.
5. Evaluate impact on Wildtrack and Unity against PR 5 once a producer sets R.

### Tasks Not started

#### PR 8: Dataset and testing

- Base `feature/prob-tracking-extracted-3d`: final accuracy and performance evaluation, then merge to `main`.

#### Parallel 1: Dataset with diverse motion

- Adopt a Tracker Evaluation dataset with more diverse motion (cars), merged into `feature/prob-tracking-extracted` for the final evaluation.
