<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# PR 3 robot-vision test plan

## High level details

- Branch: `tdorau/prob-tracking-extracted-rv-tests` (steps 1–3) and `tdorau/imm-ukf-improvements` (step 4), both into `feature/prob-tracking-extracted` @ `736c28e13`; F-2, F-7, F-6 and E-1 committed directly to `feature/prob-tracking-extracted` (`6277c8cf5`, `68f5d696d`, `c4393854f`, `a222bd748`).
- PRs: #2048 (`robot_vision` tests: split by component, add scenario tools and UKF/IMM coverage), #2056 (IMM-UKF improvements & fixes, merged as `5abb80adb`).
- Commit: values last measured at `68f5d696d`.
- Tests and test-first fixes in `controller/src/robot_vision/test` for [PR 3](prob-tracking-post-review-plan.md#pr-3-imm-ukf) of the post-review plan.

### Context

- IDs: C-n coverage tests (step 3), F-n fix + verification test (step 4), E-n evaluations; the post-review plan and tuning guide cite them.
- Steps: 1 split `TrackingTests.cpp`, 2 test tools in `support/`, 3 coverage tests passing on current code, 4 one test + fix pair per fix.
- Test-first: the failing test lands first, then the fix with before / after values in its commit message; tests waiting on a decision pin current behaviour.
- Fixes are ordered so that each one is calibrated on top of the previous ones ("order N" below).
- Verification: `make -C tracker test-robot-vision`; `RobotVisionTests --gtest_filter=...` while iterating; `RV_SCENARIO_DIR` to record scenarios.
- Out of scope: changes outside `controller/src/robot_vision` (Controller and Tracker yaw publish switch, yaw review 4: PR 4), ADR and `how-to-configure-tracker.md` wording (prob review 4), best-model vs mixture covariance (PR 4), rewriting the legacy tracker tests.

### Related documents

- [Post-review plan](prob-tracking-post-review-plan.md): PR split; PR 3 lists these tests and fixes with their status.
- [Visualization plan](../done/prob-tracking-viz-plan.md): `ScenarioRecorder`, plots and videos of these scenarios (#2086).
- [Tuning guide](../future/prob-tracking-imm-tuning.md): IMM-UKF tuning; §5 prerequisites reference F-n and E-n.
- [prob review](../reviews/pr-review-probabilistic-tracking.md): issues "N", coverage gaps "GN".
- [yaw review](../reviews/pr-review-yaw-fusion.md): findings "N", related issues "EN".
- [baseline](../reviews/robot-vision-tracking-algorithms.md) and [delta](../reviews/robot-vision-tracking-prob-tracking-delta.md): Section 9 items "9.N" of the robot-vision algorithm reports.

## Tasks Done

1. [Step 1](#step-1-split-trackingtestscpp): split `TrackingTests.cpp` by component (#2048).
2. [Step 2](#step-2-test-tools): header-only scenario tools in `test/support/` (#2048).
3. [Step 3](#step-3-coverage-tests): coverage tests C-1 to C-13 (#2048, #2086, `6277c8cf5`); C-12 skipped as a known issue.
4. [F-3](#f-3-per-model-predicted-measurements) (order 1): per-model predicted measurements (#2056).
5. [F-1](#f-1-per-model-process-noise) (order 2): per-model process noise (#2056).
6. [SingleJumpingDetectionTracking](#singlejumpingdetectiontracking) (order 3): mechanism found; known-issue skip since F-2.
7. [F-2](#f-2-no-yaw-update-without-orientation) (order 4): no yaw update for detections without orientation (`6277c8cf5`).
8. [F-4](#f-4-rank-orienting-yaw-by-class-probability) (order 6): won't fix.
9. [F-7](#f-7-initial-velocity-uncertainty) (order 9): velocity cap dropped (`68f5d696d`); 1 → 16 [tuning required] in PR 8.
10. [Velocity tolerance](#velocity-tolerance) (order 10): explained and seeded (`1161e771f`).
11. [F-6](#f-6-cholesky-failure-recovery) (order 7): Cholesky failure recovery (`c4393854f`).
12. [E-1](#e-1-sigma-point-weights) (order 8): κ = 3 − n kept and documented (`a222bd748`).

## Tasks In progress

1. [E-2](#e-2-constant-offset-in-sustained-turns) (order 11): constant offset in sustained turns analysed, halved by F-2; decision waits for per-sensor noise.

## Tasks Not started

1. [F-5](#f-5-process-noise-floor) (order 5): process-noise floor on size and z; [tuning required], postponed to PR 8.
2. [Re-measure pinned values](#re-measure-pinned-values): tighten the calibrated bounds as fixes land.

## Details

### Context

- Starting point (`736c28e13`): `TrackingTests.cpp` (1140 lines: legacy tracker tests, covariance-getter test, 13 multi-camera tests), `OrientationFusionTests.cpp`, `MetadataFusionTests.cpp`.
- Build: strict ISO C++20 at directory scope (designated initializers, `std::numbers::pi`); `-fno-access-control` gives tests access to private members.
- CI runs `make -C tracker test-robot-vision` and builds the Controller image on any `controller/src/robot_vision/**` change. Tracker-level `track()` is slow in debug builds, so filter tests drive `MultiModelKalmanEstimator` directly.
- Upstream: PR 2 merged without streaming fusion (#2061), so its streaming tests are gone; #2086 added `ScenarioRecorder` and C-10 to C-12; recorded detections are validated against `tracker/schema/camera-data.schema.json` (#2050, `5ccd64279`).
- The yaw review "Where to fix" table lists finding 6 (F-4) under PR 2; the post-review plan moved it to PR 3.

### Tasks Done

#### Step 1: split TrackingTests.cpp

- `MultipleObjectTrackerTests.cpp` (`git mv`, legacy tests), `MultiCameraFusionTests.cpp` (multi-camera tests and helpers), `MultiModelKalmanEstimatorTests.cpp`, shared `support/TestUtils.hpp`; `--gtest_list_tests` output unchanged.

#### Step 2: test tools

- `TestUtils.hpp`: `atMs`, `atSeconds`, `makeDetection`, `productionConfig()` (q = 1e-4, r = 0.2, P0 = 1, CV + CA + CTRV), `idx` state indices, `minEigenvalue`.
- `Scenario.hpp`: `Trajectory` (straight, accelerate, turn; `kCar` / `kPerson` boxes) → `Sensor` (seeded noise, orienting flag) → `observe` / `between` → `FilterRun` (`feed`, `coast`, `state`, optional recorder); sanity tests in `ScenarioSupportTest`.

#### Step 3: coverage tests

Production config with all three models unless noted; bounds relational where possible, otherwise calibrated with margin ([pinned values](#re-measure-pinned-values)).

| #    | File / test                                                                       | Covers                                                                    |
| ---- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| C-1  | `UnscentedKalmanFilterTests` / `SetStateAndCovarianceOverwritesFilterState`       | State write-back (yaw review E1)                                          |
| C-2  | `UnscentedKalmanFilterTests` / `LinearModelMatchesExactKalmanFilter`              | UKF equals an exact linear KF (prob review 5)                             |
| C-3  | `MultiModelKalmanEstimatorTests` / `PredictMixesModelStates`                      | IMM mixing (yaw review E1)                                                |
| C-4  | `MultiModelKalmanEstimatorTests` / `ReinitializeDoesNotDuplicateFilters`          | Re-initialisation (prob review G14)                                       |
| C-5  | `MultiModelKalmanEstimatorTests` / `InitialCovarianceUsesMeasurementNoiseAndCaps` | Initial covariance (prob review G14, 4)                                   |
| C-6  | `MultiModelKalmanEstimatorTests` / `ProcessNoisePerModelShape`                    | Q shape per model (prob review G8); F-1, F-5                              |
| C-7  | `MotionScenarioTests` / `TracksMotionCases`                                       | Eight motion cases, one table row each                                    |
| C-8  | `MotionScenarioTests` / `ConstantVelocityConvergence`                             | Velocity tolerance (prob review 5)                                        |
| C-9  | `MotionScenarioTests` / `TargetBornMovingAcquiresSpeed`                           | Velocity at birth (delta 9.2); [F-7](#f-7-initial-velocity-uncertainty)   |
| C-10 | `MotionScenarioTests` / `SteadyMotionHasNoConstantTrailingOffset`                 | Straight-line offset                                                      |
| C-11 | `MotionScenarioTests` / `DetectionLatencyLeavesConstantTrailingOffset`            | Latency offset = speed × lag (mechanism)                                  |
| C-12 | `MotionScenarioTests` / `SteadyCircleHasNoConstantOffset`                         | Offset in turns; skipped ([E-2](#e-2-constant-offset-in-sustained-turns)) |
| C-13 | `YawEstimationTests` / `CameraOnlyTurningYawStaysBounded`                         | Camera-only yaw bounded ([F-2](#f-2-no-yaw-update-without-orientation))   |

#### F-3: per-model predicted measurements

- Fix (yaw review E2): fixed-size `cv::Matx` in `TrackedObject`, so copies own their data; move-only `MultiModelKalmanEstimator`.
- Tests: `PredictKeepsPerModelPredictedMeasurements`, `IsMoveOnly`, CA rows of `ModelSelection`. Before, all models shared CTRV's buffer (errors 0.047 / 0.043 m); CA on acceleration 0.32 → 0.53.

#### F-1: per-model process noise

- Fix (`2804edf78`; yaw review E3, delta 9.8): each model's Q follows its own mixed velocity; CA acceleration noise, CTRV turn-rate noise 0.1 (rad/s)²/s, 1e-6/s floor on reset states.
- Tests: `ModelSelection`, `TurningTargetLearnsTurnRate`, `CoastingAfterTurn`, `OrientingSensorFollowsTurningHeading`, `OrientingSensorFollowsRotationInPlace`, `CovarianceStaysPositiveDefinite`, guard `StraightLineMatchesConstantVelocityFilter`, `ProcessNoisePerModelShape`, `PredictAppliesPerModelProcessNoise`.
- Before → after: CTRV in a 5 m/s car turn .18 → .57, turn rate 0 → 0.38 rad/s, coast after a turn 2.07 → 1.43 m, orienting yaw after a 58 s circle 1.82 → 0.07 rad. The five bug tests also fail on `main` (`5d80db465`).

#### SingleJumpingDetectionTracking

- Order 3: the legacy `MultipleObjectTrackerTests` test (15 → 200 m/s jump, r = 1e-4, 10 ms frames) passed from F-1 on only because camera frames corrected yaw with a fake measurement, which at r = 1e-4 held CTRV's turn rate at 0. It had failed since `254afe920`.
- Without it (F-2) the UKF puts the 2 m-per-frame jump, a 200-sigma innovation, into CTRV's turn rate: the velocity flips to −160 m/s and the detection starts a new track at 1360 ms. With r = 0.2 the track splits with and without F-2.
- Known-issue skip since `6277c8cf5`: one track required before the jump, skipped when the track splits after it. Holding the track would need an outlier-robust update.

#### F-2: no yaw update without orientation

- Fix (`6277c8cf5`; yaw review 2): `UnscentedKalmanFilterMod::correct(measurement, observedRows)` restricts the cross-covariance, S and the innovation to the observed rows. The estimator leaves the yaw row out of the update and the model likelihood when the prepared detection has no usable orientation (none, or dropped by the speed gate); orienting detections keep the full update. ADR 0017 wording fixed.
- Tests: `YawEstimationTests` / `CameraOnlyUpdateLeavesYawUntouched` (per-model yaw and `P_yaw` unchanged by a camera update; before, each frame cut `P_yaw` by 3 % with CV and 14–19 % with three models and moved the model yaws by 0.015 rad) and `CameraOnlyPeriodKeepsLidarResponsive` (1 s of LiDAR after 10 s of camera reaches 0.33 → 0.49 rad of a 0.5 rad step, 0.37 right after birth). `CameraOnlyTurningYawStaysBounded` passes before and after: C-13.
- Before → after (camera-only, 10 seeds): position RMS in the turn 0.27 → 0.18, manoeuvre 0.24 → 0.20, car circle 0.24 → 0.18, person turn 0.30 → 0.16, rectangular path 0.33 → 0.24 m; CTRV turn rate 0.38 → 0.42 rad/s in the 0.5 rad/s car circle, 0.03 → 0.24 rad/s in the 0.4 rad/s person turn; final speed after a turn +0.03 to +0.09 m/s; straight cases within ±4 %. C-12 car and person circles within 0.15 m. F-1 had already removed most of the slow LiDAR response measured in the yaw review (0.05 rad after 1 s).
- Follow-up: the unobserved yaw variance of camera-only tracks keeps growing (standing car 41 rad² after 10 min); [tuning required] in the post-review plan, PR 8.

#### F-4: rank orienting yaw by class probability

- Won't fix (yaw review 6): the Tracker service never sets `classification`, so `applyOrientingYaw` ranks by camera order there. Only the Controller (to be deprecated) builds `[c, 1−c]`, which misranks only when two orienting detections of one track arrive in one chunk and one has c < 0.5. `OrientingYawRanksByDetectedClassConfidence` not added.

#### F-7: initial velocity uncertainty

- Order 9 (delta 9.2), split. Fix (`68f5d696d`): the 0.05 velocity cap dropped, so the initial velocity variance is `init_state_covariance` (production 1, as on main); acceleration, yaw and yaw rate keep their caps.
- Problem: with the cap (σ 0.22 m/s) a new track starts at rest and the correction moves its position instead of its velocity; after 3–4 frames the object is out of the gate and the track restarts, again and again. A regression against main: with the services' 2 m Euclidean gate at 10 fps a car entering at 8 or 10 m/s made 11 or 14 tracks and never became reliable (main: one track).
- After (5 seeds): one track at 8 m/s, 3.8 at 10 m/s; position RMS −2 to −19 % at 10 fps and −9 to −55 % at 2 fps; coasts and the standing gate unchanged.
- Tests: `MultipleObjectTrackerTests` / `CarEnteringAtSpeedGetsOneReliableTrack` (8 m/s through the 2 m gate; 11 tracks before), C-9 tightened to ≥ 8.5 m/s (4.98 → 9.06), C-5 pins the velocity variance to `init_state_covariance`, C-7 position bounds tightened.
- Rest: 1 → 16 m²/s² (σ 4 m/s) [tuning required], post-review plan PR 8; PR 4 checks its entering scenarios with 1.
- Sweep of the initial velocity variance 0.05 / 1 / 4 / 16 / 64 m²/s² (PR 4 association scenarios, `bf8aee1d4` with a temporary override, 10 seeds):
  - fastest entry kept at 10 fps with Mahalanobis 3 / 6 / 10 / 15 / 25 m/s; Euclidean stops at 15 m/s, its fixed 2 m gate limits the first frame;
  - from 16 Mahalanobis also keeps 10 m/s at 2 fps;
  - C-9: speed 1 s after a 10 m/s entry 4.98 / 9.06 / 9.78 / 9.94 / 9.98 m/s;
  - side-by-side, standing-pair and crossing scenarios unchanged; at 4 and 16 all other robot-vision tests pass except C-5 and PR 4's `PositionMahalanobisPrefersAlongTrackAxis`.
- Cost of 16: a young track's coast gate is rounder (along / across 2.7 → 1.5 from 4 up; 2.6 → 2.0 for an established track), which is what the cap was for.
- Evaluate on Unity and Wildtrack: at 2 fps a new track's first gate is about 6 m.
- Not fixed by it: `CarPullingAwayKeepsOneTrack` still restarts once, because a standing track's velocity barely responds to a start (PR 4 decision).

#### Velocity tolerance

- Order 10 (prob review 5): explained, not reverted (`1161e771f`). Over 300 seeds the velocity error of the four loosened `tracking_test.py` tests is 3–6× main's (median 0.005–0.012 against 0.001–0.003 m/s): the velocity noise, about 300× main's, makes the filter follow the detections for manoeuvre response. With the old tolerances (0.01, `places=2`) they would fail 15–75 % of the runs; unseeded at 0.05 about once in 2000–3000.
- `VELOCITY_TOLERANCE` documents it, the tests use seed 1 (worst 0.018 m/s), C-8 refers to it. Restoring 0.01 needs less velocity noise: [tuning required], post-review plan PR 8.

#### F-6: Cholesky failure recovery

- Order 7 (baseline 9.4). Fix (`c4393854f`): when `getSigmaPoints` cannot factorise a finite covariance, it symmetrizes it, raises its eigenvalues to max(1e-9, 1e-12 λmax), writes it back and warns once. Before, the half-factorised matrix kept inverted diagonal entries: a variance of 4 came out as 0.25.
- `UnscentedKalmanFilterTests` / `PredictRecoversFromNonPositiveDefiniteCovariance`: variance 4 with one negative variance; the other variances survive `predict()` exactly.
- Never reached so far: no failure or non-PD covariance in 2 h standing (camera, yaw variance up to 490 rad²), 1 h LiDAR, 1 h circles at 10 and 1 fps, 1 h walking at 2 fps, 30 s coasts and the jump runs; in the suite the warning comes only from its own test.

#### E-1: sigma-point weights

- Order 8 (baseline 9.4, delta 9.10): κ = 3 − n kept (`a222bd748`). The sigma points sit at √3 σ, matching a Gaussian's fourth moment; the centre weight is −3, so the mean extrapolates from the centre point; with β = 2 the covariance stays PSD. Only CTRV is nonlinear.
- κ = 3 − n vs 0 (`6277c8cf5`, 10 seeds): seven motion cases ≤ 0.001 m apart at 10 fps and ≤ 0.01 m at 2 fps, coasts identical. One CTRV step with a turn-rate uncertainty of 1 rad: mean speed 1.84 against the exact 1.82 m/s, κ = 0 2.51. Baseline 9.4's 7.2 m/s (30 × 1 s coast) no longer reproduces; both stay below 3 m/s.
- Documented in `MultiModelKalmanEstimator` and the robot_vision README; `MultiModelKalmanEstimatorTests` / `CtrvPredictionKeepsGaussianMeanUnderTurnRateUncertainty` pins it (fails with κ = 0). `CoastingKeepsPredictedSpeedWithinSamples` not added.

### Tasks In progress

#### E-2: constant offset in sustained turns

- Order 11; verification: un-skip C-12 (mean along / cross ≤ 0.15 m). Measured (`d673ef83a`, Release, 5 seeds): car circle −0.13 / −0.23, person circle −0.18 / −0.25, steady turn (3 m/s, 0.5 rad/s) −0.18 / −0.29 m.
- Mechanism: under r = 0.2 CTRV holds about half of μ (car circle CV / CA / CTRV .25 / .27 / .48), and mixing with CV and CA dilutes its turn rate (0.30 for 0.5 rad/s). CTRV alone has no offset (≤ 0.07 m); before F-1 the steady turn was at −0.37 / −0.37 m.
- The steady-turn window is dominated by the turn onset: CTRV leads from about 1.4 s into the turn, cross-track peaks at −0.44 m.
- Sensor noise (0–0.45 m, 20 seeds) does not move it; only r does: r = 0.05 gives −0.09 / −0.18, r = 0.0025 −0.02 / −0.04 m, but CA then wins every turn (μ .75).
- Not levers (cross-track still ≥ 0.1 m): Markov-predicted μ, no [min, max] rescale (CA wins, μ ≈ .9), CTRV keeping its own w in mixing, model sets {CV, CTRV} or {CA, CTRV}.
- After F-2 (`6277c8cf5`, seed 1): car circle −0.06 / −0.10, person circle −0.11 / −0.08, steady turn −0.09 / −0.17 m. The fake yaw measurement of camera frames penalised CTRV in turns and held its turn rate back; C-12 stays skipped for the steady turn.
- After F-7 (`68f5d696d`, seed 1): steady turn −0.09 / −0.15 m; circles unchanged.
- Decision: with the detection noise measured per sensor ([tuning guide](../future/prob-tracking-imm-tuning.md) §5).

### Tasks Not started

#### F-5: process-noise floor

- Order 5 (prob review 2, G9; delta 9.1): [tuning required], postponed to PR 8 (post-review plan). After 5 min standing a +0.3 m height or z step reaches 0.7 % in 2 s and 3.2 % in 10 s (main 36 % / 89 %); LiDAR yaw is not stiff any more (97 % of a step in 2 s, F-1 turn-rate noise). Covariances stay PD in 2 h runs. The Tracker publishes the filtered size and z; z gets vz noise in PR 5. Floor on size (maybe per class) and z; updates C-6.
- `MotionScenarioTests` / `LongLivedTrackFollowsSizeChange`: 5 min stationary at 10 fps, then height +0.3 m; at least 50 % of the step within 2 s, every model covariance PD (today the gain is ~1/N).

#### Re-measure pinned values

Bounds calibrated at `8f1c0d9ef` (Release, fixed seed); C-7 re-calibrated after F-1 (`838f28653`), C-7 and C-9 re-measured after F-3 (`c3c8c3f96`) and F-1 (`2804edf78`), C-7 and C-10 to C-12 at `d673ef83a`; all re-measured after F-2 (`6277c8cf5`) and F-7 (`68f5d696d`). Format: bound (measured).

| Test                                               | Bound (measured)                                                                                                                                                                                                                                                                                                              | After    |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| C-7 `TracksMotionCases`, max error / final speed   | constant velocity 0.10 / 0.03 (0.06 / 0.011), acceleration 0.35 / 0.01 (0.29 / 0.006), turn 0.45 / 0.05 (0.37 / 0.019), sudden stop 0.9 / 0.05 (0.75 / 0.038), manoeuvre 0.45 / 0.2 (0.37 / 0.152), car circle 0.50 / 0.25 (0.41 / 0.172), person turn 0.35 / 0.12 (0.25 / 0.090), rectangular path 0.65 / 0.3 (0.49 / 0.229) | F-5, E-2 |
| C-8 `ConstantVelocityConvergence`                  | 0.05 m/s (CV 0.008 / 0.003, three models 0.008 / 0.002; one seed)                                                                                                                                                                                                                                                             | PR 8     |
| C-9 `TargetBornMovingAcquiresSpeed`                | ≥ 8.5 m/s (9.06; 4.98 before F-7)                                                                                                                                                                                                                                                                                             | PR 8     |
| C-6 `ProcessNoisePerModelShape`                    | Pinned formula; zero position, z and size noise                                                                                                                                                                                                                                                                               | F-5      |
| C-5 `InitialCovarianceUsesMeasurementNoiseAndCaps` | Velocity init_state_covariance; caps 0.1 acceleration, 0.05 yaw, 0.01 yaw rate (exact)                                                                                                                                                                                                                                        | PR 8     |
| C-10 `SteadyMotionHasNoConstantTrailingOffset`     | ≤ 0.15 m (−0.003 / +0.004); the steady turn moves back here once E-2 passes                                                                                                                                                                                                                                                   | E-2      |
| F-1 `ModelSelection`                               | CV margin ≥ .03 / .05 (.047 / .090); CA μ ≥ .45 (.56 / .62); CTRV μ ≥ .45 / .40 (.56 / .48), margin ≥ .2 / .1 (.34 / .21); turn exit margin ≥ .03 (.066)                                                                                                                                                                      | F-5      |
| F-1 `TurningTargetLearnsTurnRate`                  | w in [0.3, 0.6] (0.41), [−0.45, −0.15] (−0.24), ±0.05 (−0.003)                                                                                                                                                                                                                                                                | F-5      |
| F-1 `CoastingAfterTurn`                            | ≤ 1.8 m (1.17)                                                                                                                                                                                                                                                                                                                | E-1, F-5 |
| F-1 `OrientingSensorFollowsTurningHeading`         | ≤ 0.2 rad (0.07), model yaw spread ≤ 0.3 (0.15)                                                                                                                                                                                                                                                                               | F-5      |
| F-1 `OrientingSensorFollowsRotationInPlace`        | ≥ 0.35 / 0.45 rad (0.42 / 0.50)                                                                                                                                                                                                                                                                                               | F-5      |
| F-1 `StraightLineMatchesConstantVelocityFilter`    | ratio ≤ 1.1 (1.05 / 1.07 / 1.03; a single seed varies by about 0.2)                                                                                                                                                                                                                                                           | F-5      |
| C-13 `CameraOnlyTurningYawStaysBounded`            | yaw variance ≤ 0.2 rad² (0.13), model yaw spread ≤ 0.3 rad (0.17)                                                                                                                                                                                                                                                             | PR 8     |
