<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# PR 3 robot-vision test plan

## High level details

- Branch: `tdorau/prob-tracking-extracted-rv-tests` (steps 1–3) and `tdorau/imm-ukf-improvements` (step 4), both into `feature/prob-tracking-extracted` @ `736c28e13`.
- PRs: #2048 (`robot_vision` tests: split by component, add scenario tools and UKF/IMM coverage), #2056 (IMM-UKF improvements & fixes, merged as `5abb80adb`).
- Commit: values last measured at `d673ef83a`.
- Tests and test-first fixes in `controller/src/robot_vision/test` for [PR 3](prob-tracking-post-review-plan.md#pr-3-imm-ukf) of the post-review plan.

### Context

- IDs: C-n coverage tests (step 3), F-n fix + verification test (step 4), E-n evaluations; the post-review plan and tuning guide cite them.
- Steps: 1 split `TrackingTests.cpp`, 2 test tools in `support/`, 3 coverage tests passing on current code, 4 one test + fix pair per fix.
- Test-first: the failing test lands first, then the fix with before / after values in its commit message; tests waiting on a decision pin current behaviour.
- Fixes are ordered so that each one is calibrated on top of the previous ones ("order N" below).
- Verification: `make -C tracker test-robot-vision`; `RobotVisionTests --gtest_filter=...` while iterating; `RV_SCENARIO_DIR` to record scenarios.
- Out of scope: changes outside `controller/src/robot_vision` (Controller yaw publish switch, yaw review 4), Python `tracking_test.py` tolerances, ADR and `how-to-configure-tracker.md` wording (prob review 4), best-model vs mixture covariance (PR 4), rewriting the legacy tracker tests.

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
3. [Step 3](#step-3-coverage-tests): coverage tests C-1 to C-12 (#2048, #2086); C-12 skipped as a known issue.
4. [F-3](#f-3-per-model-predicted-measurements) (order 1): per-model predicted measurements (#2056).
5. [F-1](#f-1-per-model-process-noise) (order 2): per-model process noise (#2056).

## Tasks In progress

1. [F-7](#f-7-initial-velocity-uncertainty) (order 9): initial velocity uncertainty; sweep done, proposal 16 m²/s² without the cap.
2. [Velocity tolerance](#velocity-tolerance) (order 10): C-8 pins the loosened tolerance; investigation open.
3. [E-2](#e-2-constant-offset-in-sustained-turns) (order 11): constant offset in sustained turns analysed; decision waits for per-sensor noise.

## Tasks Not started

1. [SingleJumpingDetectionTracking](#singlejumpingdetectiontracking) (order 3): passes since F-1; find the mechanism.
2. [F-2](#f-2-no-yaw-update-without-orientation) (order 4): no yaw update for detections without orientation.
3. [F-5](#f-5-process-noise-floor) (order 5): process-noise floor on position, z and size.
4. [F-4](#f-4-rank-orienting-yaw-by-class-probability) (order 6): rank orienting yaw by detected-class probability.
5. [F-6](#f-6-cholesky-failure-recovery) (order 7): recover from a failed Cholesky factorisation.
6. [E-1](#e-1-sigma-point-weights) (order 8): evaluate the sigma-point weights (κ).
7. [Re-measure pinned values](#re-measure-pinned-values): tighten the calibrated bounds as fixes land.

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

#### F-3: per-model predicted measurements

- Fix (yaw review E2): fixed-size `cv::Matx` in `TrackedObject`, so copies own their data; move-only `MultiModelKalmanEstimator`.
- Tests: `PredictKeepsPerModelPredictedMeasurements`, `IsMoveOnly`, CA rows of `ModelSelection`. Before, all models shared CTRV's buffer (errors 0.047 / 0.043 m); CA on acceleration 0.32 → 0.53.

#### F-1: per-model process noise

- Fix (`2804edf78`; yaw review E3, delta 9.8): each model's Q follows its own mixed velocity; CA acceleration noise, CTRV turn-rate noise 0.1 (rad/s)²/s, 1e-6/s floor on reset states.
- Tests: `ModelSelection`, `TurningTargetLearnsTurnRate`, `CoastingAfterTurn`, `OrientingSensorFollowsTurningHeading`, `OrientingSensorFollowsRotationInPlace`, `CovarianceStaysPositiveDefinite`, guard `StraightLineMatchesConstantVelocityFilter`, `ProcessNoisePerModelShape`, `PredictAppliesPerModelProcessNoise`.
- Before → after: CTRV in a 5 m/s car turn .18 → .57, turn rate 0 → 0.38 rad/s, coast after a turn 2.07 → 1.43 m, orienting yaw after a 58 s circle 1.82 → 0.07 rad. The five bug tests also fail on `main` (`5d80db465`).

### Tasks In progress

#### F-7: initial velocity uncertainty

- Order 9 (delta 9.2): drop the 0.05 velocity cap so that `init_state_covariance` sets the initial velocity variance, and raise the production value 1 → 16 m²/s² (σ 4 m/s); acceleration, yaw and yaw rate keep their caps.
- Problem: with the cap (σ 0.22 m/s) a new track starts at rest and the correction moves its position instead of its velocity; after 3–4 frames the object is out of the gate and the track restarts, again and again. At 10 fps objects entering faster than about 5 m/s (Euclidean) or 3 m/s (Mahalanobis, whose new-track gate is about 1.6 m) never get a reliable track: PR 4 `RunnerEnteringGetsOneTrack` and `CarEnteringAtSpeedGetsOneTrack`, skipped as known issues.
- Sweep of the initial velocity variance 0.05 / 1 / 4 / 16 / 64 m²/s² (PR 4 association scenarios, `bf8aee1d4` with a temporary override, 10 seeds):
  - fastest entry kept at 10 fps with Mahalanobis 3 / 6 / 10 / 15 / 25 m/s; Euclidean stops at 15 m/s, its fixed 2 m gate limits the first frame;
  - from 16 Mahalanobis also keeps 10 m/s at 2 fps;
  - C-9: speed 1 s after a 10 m/s entry 4.98 / 9.06 / 9.78 / 9.94 / 9.98 m/s;
  - side-by-side, standing-pair and crossing scenarios unchanged; at 4 and 16 all other robot-vision tests pass except C-5 and PR 4's `PositionMahalanobisPrefersAlongTrackAxis`.
- Cost: a young track's coast gate is rounder (along / across 2.7 → 1.5 from 4 up; 2.6 → 2.0 for an established track), which is what the cap was for.
- Tests: tighten C-9 to ≥ 9.5 m/s (fails before the fix); C-5 pins the velocity variance to `init_state_covariance`; PR 4 un-skips the two entering scenarios.
- Evaluate on Unity and Wildtrack: at 2 fps a new track's first gate is about 6 m.
- Not fixed by it: `CarPullingAwayKeepsOneTrack` still restarts once, because a standing track's velocity barely responds to a start (PR 4 decision).

#### Velocity tolerance

- Order 10 (prob review 5). C-8 pins the 0.05 m/s tolerance (0.01 before `254afe920`), measured 0.008 / 0.003 m/s on one seed.
- Next: after F-7, check several seeds, then restore 0.01 or document the reason.

#### E-2: constant offset in sustained turns

- Order 11; verification: un-skip C-12 (mean along / cross ≤ 0.15 m). Measured (`d673ef83a`, Release, 5 seeds): car circle −0.13 / −0.23, person circle −0.18 / −0.25, steady turn (3 m/s, 0.5 rad/s) −0.18 / −0.29 m.
- Mechanism: under r = 0.2 CTRV holds about half of μ (car circle CV / CA / CTRV .25 / .27 / .48), and mixing with CV and CA dilutes its turn rate (0.30 for 0.5 rad/s). CTRV alone has no offset (≤ 0.07 m); before F-1 the steady turn was at −0.37 / −0.37 m.
- The steady-turn window is dominated by the turn onset: CTRV leads from about 1.4 s into the turn, cross-track peaks at −0.44 m.
- Sensor noise (0–0.45 m, 20 seeds) does not move it; only r does: r = 0.05 gives −0.09 / −0.18, r = 0.0025 −0.02 / −0.04 m, but CA then wins every turn (μ .75).
- Not levers (cross-track still ≥ 0.1 m): Markov-predicted μ, no [min, max] rescale (CA wins, μ ≈ .9), CTRV keeping its own w in mixing, model sets {CV, CTRV} or {CA, CTRV}.
- Decision: with the detection noise measured per sensor ([tuning guide](../future/prob-tracking-imm-tuning.md) §5).

### Tasks Not started

#### SingleJumpingDetectionTracking

- Order 3: the existing `MultipleObjectTrackerTests` test (15 → 200 m/s jump) passes since F-1, after failing since `254afe920`. Find the mechanism, then fix the cause or update the expectations, with the reason in the commit message.

#### F-2: no yaw update without orientation

- Order 4 (yaw review 2): reduced update without yaw for non-orienting detections; fix the ADR "predict" wording.
- `YawEstimationTests` / `CameraOnlyUpdateLeavesYawUntouched`: `P_yaw` after correct equals after predict (CV only); each model keeps its own predicted yaw (three models).
- `YawEstimationTests` / `CameraOnlyPeriodKeepsLidarResponsive`: 1 s of LiDAR at 0.5 rad after 10 s of camera moves yaw at least as much as right after birth.
- `YawEstimationTests` / `CameraOnlyTurningYawStaysBounded`: 60 s camera-only circle keeps covariances PD and yaw variance and model yaw spread bounded; moves to step 3 if it already passes.

#### F-5: process-noise floor

- Order 5 (prob review 2, G9; delta 9.1): floor on position, z and size process noise; updates C-6.
- `MotionScenarioTests` / `LongLivedTrackFollowsSizeChange`: 5 min stationary at 10 fps, then height +0.3 m; at least 50 % of the step within 2 s, every model covariance PD (today the gain is ~1/N).

#### F-4: rank orienting yaw by class probability

- Order 6 (yaw review 6): `applyOrientingYaw` ranks by the detected-class probability instead of `maxCoeff()`.
- `OrientationFusionTests` / `OrientingYawRanksByDetectedClassConfidence`: `[0.3, 0.7]` vs `[0.6, 0.4]`; today the 0.3 detection wins.

#### F-6: Cholesky failure recovery

- Order 7 (baseline 9.4): on a failed factorisation in `getSigmaPoints` symmetrize, add diagonal jitter, retry and log once.
- `UnscentedKalmanFilterTests` / `PredictRecoversFromNonPositiveDefiniteCovariance`: covariance with a negative eigenvalue, then `predict()`; finite state and `minEigenvalue(errorCov) > 0`.

#### E-1: sigma-point weights

- Order 8 (baseline 9.4, delta 9.10): κ = 3 − n vs κ = 0 after F-1; keep and document, or change.
- If κ changes: `UnscentedKalmanFilterTests` / `CoastingKeepsPredictedSpeedWithinSamples`: CTRV at 3 m/s, turn-rate variance 1, 30 predicts of 1 s; speed ≤ 3 m/s (7.2 today, 0.40 with κ = 0).

#### Re-measure pinned values

Bounds calibrated at `8f1c0d9ef` (Release, fixed seed); C-7 re-calibrated after F-1 (`838f28653`), C-7 and C-9 re-measured after F-3 (`c3c8c3f96`) and F-1 (`2804edf78`), C-7 and C-10 to C-12 at `d673ef83a`. Format: bound (measured).

| Test                                               | Bound (measured)                                                                                                                                                                                                                                                                                                              | After    |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| C-7 `TracksMotionCases`, max error / final speed   | constant velocity 0.15 / 0.03 (0.10 / 0.016), acceleration 0.45 / 0.01 (0.34 / 0.004), turn 0.65 / 0.05 (0.53 / 0.015), sudden stop 0.9 / 0.05 (0.69 / 0.037), manoeuvre 0.6 / 0.25 (0.49 / 0.175), car circle 0.65 / 0.2 (0.53 / 0.130), pedestrian turn 0.5 / 0.1 (0.43 / 0.059), rectangular path 0.8 / 0.2 (0.66 / 0.143) | F-5, E-2 |
| C-8 `ConstantVelocityConvergence`                  | 0.05 m/s (CV 0.008 / 0.003, three models 0.008 / 0.002; one seed)                                                                                                                                                                                                                                                             | Order 10 |
| C-9 `TargetBornMovingAcquiresSpeed`                | ≥ 4.5 m/s (4.98; 4.99 before F-1, 4.79 before F-3)                                                                                                                                                                                                                                                                            | F-7      |
| C-6 `ProcessNoisePerModelShape`                    | Pinned formula; zero position, z and size noise                                                                                                                                                                                                                                                                               | F-5      |
| C-5 `InitialCovarianceUsesMeasurementNoiseAndCaps` | Latent caps 0.05 velocity, 0.1 acceleration, 0.05 yaw, 0.01 yaw rate (exact)                                                                                                                                                                                                                                                  | F-7      |
| C-10 `SteadyMotionHasNoConstantTrailingOffset`     | ≤ 0.15 m (+0.02 / +0.01); the steady turn moves back here once E-2 passes                                                                                                                                                                                                                                                     | E-2      |
| F-1 `ModelSelection`                               | CV margin ≥ .03 / .05 (.054 / .105); CA μ ≥ .45 (.59 / .62); CTRV μ ≥ .45 / .40 (.57 / .48), margin ≥ .2 / .1 (.35 / .21); turn exit margin ≥ .03 (.071)                                                                                                                                                                      | F-5      |
| F-1 `TurningTargetLearnsTurnRate`                  | w in [0.3, 0.6] (0.38), [−0.45, −0.15] (−0.22), ±0.05 (−0.005)                                                                                                                                                                                                                                                                | F-5      |
| F-1 `CoastingAfterTurn`                            | ≤ 1.8 m (1.43)                                                                                                                                                                                                                                                                                                                | E-1, F-5 |
| F-1 `OrientingSensorFollowsTurningHeading`         | ≤ 0.2 rad (0.07), model yaw spread ≤ 0.3 (0.15)                                                                                                                                                                                                                                                                               | F-2, F-5 |
| F-1 `OrientingSensorFollowsRotationInPlace`        | ≥ 0.35 / 0.45 rad (0.42 / 0.50)                                                                                                                                                                                                                                                                                               | F-2, F-5 |
| F-1 `StraightLineMatchesConstantVelocityFilter`    | ratio ≤ 1.1 (1.01 / 0.83 / 1.04; a single seed varies by about 0.2)                                                                                                                                                                                                                                                           | F-5      |
