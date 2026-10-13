<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# PR 3 robot-vision test plan

Test plan for PR 3 (IMM-UKF, `feature/prob-tracking-extracted`) from [prob-tracking-post-review-plan.md](prob-tracking-post-review-plan.md).
Scope is `controller/src/robot_vision/test` only.

References follow the post-review plan: "yaw review N/EN" → [pr-review-yaw-fusion.md](pr-review-yaw-fusion.md),
"prob review N/GN" → [pr-review-probabilistic-tracking.md](pr-review-probabilistic-tracking.md),
"delta 9.N" → [robot-vision-tracking-prob-tracking-delta.md](robot-vision-tracking-prob-tracking-delta.md).

## 1. Starting point (`feature/prob-tracking-extracted` @ 736c28e13)

| File                             | Contents                                                                                                                                                                                                          |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TrackingTests.cpp` (1140 lines) | Legacy tracker tests (four distance types, stress test, `SingleJumpingDetectionTracking` - known failing since 254afe920); PR 3 covariance-getter test; 13 multi-camera tests from `multi-camera-geometry-fusion` |
| `OrientationFusionTests.cpp`     | Tracker-level yaw: `prepareYawMeasurement`, `applyOrientingYaw`, speed gate                                                                                                                                       |
| `MetadataFusionTests.cpp`        | Metadata fusion policy                                                                                                                                                                                            |

- Existing helpers: `makeFusionTracker`, `makeBox(..., cameraId)`, `averageOf`, `expectSameState`, `expectSameSingleTrack` (twin-tracker pattern), `tracksSortedByX`, `atMs`; `OrientationFusionTests.cpp` has its own `makeDetection` and a duplicate `atMs`.
- robot_vision builds as strict ISO C++20 (`CMAKE_CXX_EXTENSIONS OFF`) at directory scope, covering the library, Python bindings, tests and benchmarks (736c28e13). Test code can use designated initializers (in declaration order) and `std::numbers::pi` instead of the non-standard `M_PI`. `-fno-access-control` lets tests reach private members.
- CI runs `make -C tracker test-robot-vision`, and builds the Controller image and imports `robot_vision` whenever `controller/src/robot_vision/**` changes (also for test-only changes). Tracker-level `track()` calls are slow in debug builds, so filter tests drive `MultiModelKalmanEstimator` directly.
- PR 4 tests (3792d25d5) build a track, coast it and read `predictedMeasurementCov`, single CV model only. The tools below are sized to cover that as well.

## 2. Branches and commit order

| Step | Content                                     | Branch                                                                                                                                               |
| ---- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Split `TrackingTests.cpp` (pure move)       | `tdorau/prob-tracking-extracted-rv-tests` (off `feature/prob-tracking-extracted` @ 736c28e13), merged into `feature/prob-tracking-extracted` as a PR |
| 2    | Test tools (`support/`)                     | same                                                                                                                                                 |
| 3    | Coverage tests passing on current code      | same                                                                                                                                                 |
| 4    | One commit per fix: verification test + fix | directly on `feature/prob-tracking-extracted`, after the test-branch PR is merged                                                                    |

- Step 4 commits are test-first: the test is shown failing on the parent commit, then the fix lands in the same commit. Before/after values go in the commit message.
- Tests whose final bound depends on a pending decision (C-6, C-8, C-9) land in step 3 pinning current behaviour; the fix commit updates them, and the updated version must fail without the fix.
- Verification per step: `make -C tracker test-robot-vision`; filtered `RobotVisionTests --gtest_filter=...` while iterating.

## 3. Step 1: split `TrackingTests.cpp`

| New file                                                   | Moved from `TrackingTests.cpp`                                                                                                                                         |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `MultipleObjectTrackerTests.cpp` (`git mv`, keeps history) | Legacy tracker and stress tests, unchanged; `createObjectAtLocation` stays local                                                                                       |
| `MultiCameraFusionTests.cpp`                               | The 13 multi-camera tests with `makeFusionTracker`, `averageOf`, `expectSameState`, `expectSameSingleTrack`, `tracksSortedByX`, `kFusionGate` (local, only used there) |
| `MultiModelKalmanEstimatorTests.cpp`                       | Covariance-getter test                                                                                                                                                 |
| `support/TestUtils.hpp`                                    | Shared `atMs` (replaces the duplicate in `OrientationFusionTests.cpp`), `makeBox`                                                                                      |

- Update `TEST_SOURCES` in `test/CMakeLists.txt`; the C++ standard is inherited from the directory scope, so no per-target settings are added.
- Check: `RobotVisionTests --gtest_list_tests` output is identical before and after.

## 4. Step 2: test tools (header-only, `support/`)

`support/TestUtils.hpp`, in addition to the moved helpers:

- `atSeconds(double)`.
- `productionConfig()`: the existing `TrackManagerConfig` with the Controller / Tracker service values (q = 1e-4, r = 0.2, P0 = 1, CV + CA + CTRV). One type drives both `FilterRun` and a `MultipleObjectTracker` (PR 4).
- `namespace idx { X, Y, Vx, Vy, Ax, Ay, Z, Length, Width, Height, Yaw, YawRate }`: state-vector indices for Q / P0 / variance assertions.
- `minEigenvalue(const cv::Mat &)`: positive-definiteness checks (here: long-run and yaw tests; PR 4: degenerate covariance, prob review G6).

`support/Scenario.hpp`, composed as truth → sensor → filter run:

```cpp
// Unicycle truth (straight / accelerate / turn segments), finely integrated, sampled at fps.
auto truth = Trajectory(/*x*/ 0, /*y*/ 0, /*heading*/ 0, /*speed*/ 5)
               .straight(3).turn(0.5, 3).accelerate(-10, 1).straight(2) // turn, then sudden stop
               .sample(10.0);                                           // std::vector<TruthSample>

Sensor camera;                        // position noise std, orienting flag, box size, seeded RNG
Sensor lidar{.orienting = true};      // reports heading as yaw, sets has_orientation

FilterRun run(productionConfig());    // wraps MultiModelKalmanEstimator; initializes on the first observation
auto states = run.feed(observe(between(truth, 0, 10), camera)); // one snapshot per update (cv::Mat cloned)
run.feed(observe(between(truth, 10, 11), lidar));               // switch sensor mid-run
run.coast(1.0);                                                 // predict only
run.state();                                                    // combined state; run.estimator for per-model access
```

- `Trajectory` has only `straight`, `accelerate`, `turn`; speed is clamped at 0, so a stop is `accelerate(-a, t)` and standing is `straight` at speed 0.
- `Sensor` and the C-7 case table are plain aggregates set up with designated initializers, e.g. `{.name = "turn", .truth = ..., .maxPositionError = 0.3}`, so no builder methods or constructors are needed.
- `between(samples, t0, t1)` slices time. Sensor switches and reported-value changes (e.g. a height step) are done by editing the `Sensor` between `feed` calls, so no concatenation or callback API is needed.
- Snapshots clone their matrices to avoid the shared `cv::Mat` buffer pitfall (yaw review E2).
- PR 4 uses: `FilterRun` + `Trajectory` + `coast` for Mahalanobis gate tests with all three models (prob review G2, G7), competing tracks (G10), the radius ceiling (G4) and the mixture vs best-model covariance evaluation during a turn; an orienting `Sensor` near ±π for the yaw-wrap test (yaw review 3).
- Not added: a tracker-level runner (no PR 3 or PR 4 test needs it). The reference linear Kalman filter stays local to its only test (C-2).
- Sanity test `ScenarioSupportTest.TrajectoryKinematics`: a circle closes after 2π/ω (`std::numbers::pi`), braking clamps speed at 0.

## 5. Step 3: coverage tests (test branch)

Unless noted, tests use `productionConfig()` with all three models, so `predictState()` is exercised (post-review plan: "{CV, CA, CTRV}"). Bounds are relational (run A vs run B) where possible, otherwise calibrated with margin.

| #   | File / test                                                                       | Plan item                                                              | Asserts                                                                                                                                                             |
| --- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C-1 | `UnscentedKalmanFilterTests` / `SetStateAndCovarianceOverwritesFilterState`       | yaw review E1                                                          | Read-back after `setStateAndCovariance` (fails on `main`)                                                                                                           |
| C-2 | `UnscentedKalmanFilterTests` / `LinearModelMatchesExactKalmanFilter`              | prob review 5 (rules out the UKF as the cause of the looser tolerance) | UKF with CV model and fixed Q equals an exact linear KF to 1e-9 over 30 updates (fails on `main`)                                                                   |
| C-3 | `MultiModelKalmanEstimatorTests` / `PredictMixesModelStates`                      | yaw review E1, {CV, CA, CTRV}                                          | After models diverge, `predict(0)` leaves each model at Σᵢ μ(i\|j)·xᵢ from `getConditionalProbability()` (fails on `main`)                                          |
| C-4 | `MultiModelKalmanEstimatorTests` / `ReinitializeDoesNotDuplicateFilters`          | prob review G14                                                        | A second `initialize()` keeps one filter per model (fails on `main`)                                                                                                |
| C-5 | `MultiModelKalmanEstimatorTests` / `InitialCovarianceUsesMeasurementNoiseAndCaps` | prob review G14, pins semantics documented for prob review 4           | Measured states start at r; latent states at min(P0, cap) for P0 = 100 and P0 = 1e-3                                                                                |
| C-6 | `MultiModelKalmanEstimatorTests` / `KinematicProcessNoise...` (table)             | prob review G8                                                         | Near-zero-velocity fallback to the x axis, rotation for diagonal motion, linear dt scaling, `qVel` floor, current zero position/size entries. F-1 and F-5 update it |
| C-7 | `MotionScenarioTests` / `TracksMotionCases` (table + `SCOPED_TRACE`)              | manoeuvres, sudden stops                                               | Constant velocity, acceleration, turn, braking to a stop, combined manoeuvre: max position error after warm-up, final velocity error. New cases are one table row   |
| C-8 | `MotionScenarioTests` / `ConstantVelocityConvergence`                             | prob review 5                                                          | Gtest mirror of the loosened Python tests (seeded noise). Pins the current tolerance; the step 4 investigation either restores 0.01 or documents the reason         |
| C-9 | `MotionScenarioTests` / `TargetBornMovingAcquiresSpeed`                           | delta 9.2                                                              | Target born at 10 m/s, speed after 1 s. Pins current behaviour; tightened only if the 0.05 velocity prior cap is changed                                            |

## 6. Step 4: fix + verification test pairs (`feature/prob-tracking-extracted`)

Ordered so that each fix is calibrated on top of the previous ones.

| Order | #   | Fix (plan item)                                                                               | Verification test                                                              | Why it fails without the fix                                                                                                                                                                                                                             |
| ----- | --- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | F-3 | Per-model predicted-measurement buffers in `initialize()` (yaw review E2)                     | `MultiModelKalmanEstimatorTests` / `PredictKeepsPerModelPredictedMeasurements` | After models diverge and `coast(0.5)`: each model's predicted measurement must equal h(its state), and the combined one h(combined state). Today all models share CTRV's buffer. First because it changes model likelihoods, which F-1 tuning depends on |
| 2     | F-1 | Per-model process noise incl. yaw and yaw rate (yaw review E3, delta 9.8)                     | `MotionScenarioTests` / `TurningTargetLearnsTurnRate`                          | Camera-only circle at ω = 0.5 rad/s: estimated `w` stays near 0 today. Optionally also CTRV has the highest model probability during the turn. Updates C-6                                                                                               |
| 3     | -   | `SingleJumpingDetectionTracking`                                                              | existing test                                                                  | Recheck after F-1; then fix the cause or update the expectations, with the reason in the commit message                                                                                                                                                  |
| 4     | F-2 | Reduced update without yaw for non-orienting detections; ADR "predict" wording (yaw review 2) | `YawEstimationTests` / `CameraOnlyUpdateLeavesYawUntouched`                    | CV only: `P_yaw` after correct equals after predict, exactly. Three models: each model's yaw equals its own predicted yaw. Today the update shrinks `P_yaw` and pulls models to the combined yaw                                                         |
|       |     |                                                                                               | `YawEstimationTests` / `CameraOnlyPeriodKeepsLidarResponsive`                  | Run A: 10 s camera, then 1 s LiDAR at 0.5 rad. Run B: 1 s LiDAR right after birth. Expect yaw_A ≥ yaw_B; today A is much less responsive                                                                                                                 |
|       |     |                                                                                               | `YawEstimationTests` / `CameraOnlyTurningYawStaysBounded`                      | 60 s camera-only circle with mixing: all model covariances PD, yaw variance and model yaw spread below a calibrated bound. If it already passes on current code it moves to step 3 as coverage                                                           |
| 5     | F-5 | Process-noise floor on position, z and size (prob review 2, G9, delta 9.1)                    | `MotionScenarioTests` / `LongLivedTrackFollowsSizeChange`                      | 5 min stationary at 10 fps (estimator only), then height +0.3 m: at least 50 % of the step within 2 s and every model covariance PD. Today the gain is ~1/N. Updates C-6                                                                                 |
| 6     | F-4 | Rank orienting yaw by detected-class probability in `applyOrientingYaw` (yaw review 6)        | `OrientationFusionTests` / `OrientingYawRanksByDetectedClassConfidence`        | Two-class `[0.3, 0.7]` vs `[0.6, 0.4]`: `maxCoeff()` picks the 0.3 detection                                                                                                                                                                             |
| 7     | -   | Velocity tolerance (prob review 5), velocity prior cap (delta 9.2)                            | C-8, C-9                                                                       | Tightened only if the investigation produces a fix                                                                                                                                                                                                       |

Note: the yaw review "Where to fix" table lists finding 6 under PR 2; the post-review plan moved it into PR 3.

## 7. Out of scope

- Changes outside `controller/src/robot_vision`, including the Controller yaw publish switch (post-review plan "yaw thresholding when unreliable", yaw review 4).
- Python `tests/sscape_tests/robot_vision/tracking_test.py` tolerances (PR 3, outside this folder, and that folder does not run in CI).
- ADR and `how-to-configure-tracker.md` wording (prob review 4).
- Best-model vs mixture covariance tests (PR 4).
- Rewriting the copy-pasted legacy tracker tests.
