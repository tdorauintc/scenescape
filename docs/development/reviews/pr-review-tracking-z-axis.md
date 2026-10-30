<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# PR Review: non-planar Z / `vz` tracking (`feature/prob-tracking-extracted-3d`)

- **Source**: `feat/tracking-z-axis` (6 commits by Sarat Poluri, `097f5ab81`..`4e29a8407`), based on `feature/prob-tracking-extracted-association` @ `f6c137481` (Oct 7, 66 commits behind).
- **New branch**: `feature/prob-tracking-extracted-3d` (work branch `tdorau/prob-tracking-extracted-3d`) = the z-axis commits cherry-picked onto the updated association branch, without their own Tracker Service 3D detection input, + 3 commits from this review. Tracker 3D input came later through main (#2050) and was merged with a follow-up fix (E5).
- **Base**: `feature/prob-tracking-extracted-association` @ `1fd627aa2` (includes #2103 and #2050). Originally ported onto `ab0caa89c`.
- **Size** (vs base @ `1fd627aa2`): 39 files, +1480 / −287.

References: "prob review N" → [pr-review-probabilistic-tracking.md](pr-review-probabilistic-tracking.md), "yaw review N" → [pr-review-yaw-fusion.md](pr-review-yaw-fusion.md), "PR N" → [prob-tracking-post-review-plan.md](../plans/prob-tracking-post-review-plan.md).

## 1. Scope of changes

| Area               | Change                                                                                                                                                                                                                                                                                                      |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| robot_vision state | 13-state UKF `[x, y, vx, vy, ax, ay, z, vz, l, w, h, yaw, yaw_rate]`; named `StateIndex` / `MeasurementIndex`; CV/CA/CTRV integrate `z += vz·dt`, CP zeroes `vz`                                                                                                                                            |
| robot_vision noise | `P0(vz) = min(init, 0.05)`; `Q(vz) = q_vel·dt` (same scale as the stationary along-track velocity noise)                                                                                                                                                                                                    |
| Association        | `Euclidean`, `MultiClassEuclidean` and the `max_radius_m` ceiling become XYZ; `PositionMahalanobis` becomes 3×3 with χ²(p, 3) (11.34 at p = 0.99)                                                                                                                                                           |
| Birth clustering   | New `DistanceType::EuclideanBirth`: XY unless both detections have `zMeasured`, then XYZ (2 m radius)                                                                                                                                                                                                       |
| `isDynamic`        | Uses 3D speed (`vz` counts toward dynamic/static coast aging)                                                                                                                                                                                                                                               |
| Controller         | `chi2_threshold(p, 3)` for matching, `(p, 2)` for the UI window; publishes `velocity[2] = vz`; `zMeasured` = detection has `translation`                                                                                                                                                                    |
| Tracker service    | Publishes `vz`; χ² df 3 / df 2 split as in the Controller; translation detections from #2050 set `zMeasured` (E5). The original z-axis 3D detection input was dropped in favour of #2050 (Z5)                                                                                                               |
| Tests              | gtest: climb, coast, constant-z, stacked floors, hybrid birth, χ²(3); Python: `tracking_test.py`, `test_ilabs_tracking.py`, `test_moving_object.py`; Tracker unit: χ² df split, publisher `vz`, `zMeasured`, stacked-floor 3D detections, climbing 3D detection end to end; functional `test_z_tracking.py` |
| Docs               | `.github/plans/plan-probabilistic-tracking.md` (Z section); `tracker/docs/implementation.md` (z tracking with 3D detections)                                                                                                                                                                                |

## 2. Verification

| Check                                                                                                                                 | Association @ `ab0caa89c` | 3d @ `a0ea702b1`                        | 3d @ `ac90ba78e` (with #2050) |
| ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- | --------------------------------------- | ----------------------------- |
| `make -C tracker test-robot-vision` (gtest)                                                                                           | 47/48                     | 57/58                                   | 57/58                         |
| `make -C tracker test-unit`                                                                                                           | 501/501                   | 501/501                                 | 537/537                       |
| `pytest` on robot_vision, ilabs_tracking, moving_object, scene_controller, detections_builder (+ external_source for the last column) | -                         | 204/204                                 | 253/253                       |
| `pytest tests/sscape_tests` (full)                                                                                                    | 1831 passed, 8 failed     | 1832 passed, same 8 failed              | 2144 passed, same 8 failed    |
| `make -C tracker lint-cpp`                                                                                                            | clean                     | clean (Z8)                              | clean                         |
| Python indent check, prettier (changed files), SPDX headers                                                                           | -                         | clean                                   | clean                         |
| `tests/functional/test_z_tracking.py`                                                                                                 | -                         | **not run** (needs the container stack) | **not run**                   |

- The only gtest failure is `SingleJumpingDetectionTracking`, known failing since `254afe920`; #2056 fixes it (I3).
- The 8 Python failures are the same on all branches (E4).
- The Tracker does not build with the host GCC 11 (`<format>`), so C++ builds ran in the `tracker-builder-debug` image (GCC 14, the CI equivalent).

## 3. Issues: new functionality

**Z1 (High). Mixed planar and 3D sources are now penalised in track↔detection association.**
Planar detections report the ground point (`z = 0`), 3D detections report the detector's reference point (usually the box centre). Only birth clustering got the `zMeasured` exception; Euclidean and `PositionMahalanobis` association gate on Δz for every pair, and the filter's `z` alternates between the two references.

- Measured with production settings (CV + CA + CTRV, q = 1e-4, r = 0.2), a 3 s planar track has `S_zz ≈ 0.25 m²`. At the same XY, Δz = 0.9 m uses 29% of the χ²(3) budget, Δz = 1.5 m uses 80%, and Δz ≥ ~1.7 m is rejected outright, which splits the track.
- This hits camera + LiDAR / 3D OD fusion of one category, the main multimodal use case. With #2050 the Tracker Service has the same setup: pixel boxes are projected to z = 0, translation detections report the detector's point.
- Measured in the Tracker's batched path (one pixel camera at z = 0 and one 3D sensor at box-centre height c, production settings, 15 fps):
  - both sensors in every chunk: one track, but it publishes the midpoint height c/2, even at c = 3 m;
  - camera-only for 2 s, then 3D-only: the track splits at c = 2 m (not at 0.9 or 1.5 m);
  - sensors alternating frame by frame: one track, with spurious `vz` up to 0.16 m/s at c = 2 m.
- #2050's `Tracking_Mixed2DAnd3DMeasurementsPublishSingleTrackWith3DYaw` places both detections at z ≈ 0, so it does not cover this.
- **Fix:** gate on `z` only when the detection has `zMeasured` and the track has already been updated with measured z (a sticky flag, like `orientation_observed` for yaw), using df 2 otherwise. Also agree on one z reference (ground contact or centre) and convert at ingest.

**Z2 (Medium). Planar scenes get a wider gate.** When Δz ≈ 0, the XY gate becomes χ² = 11.34 instead of 9.21 (+11% in σ; per-axis false-reject drops from 1% to 0.34%). The author tracks this as F2 ("run Wildtrack eval"). The Z1 fix (df 2 for planar pairs) removes it.

**Z3 (Medium). The UI association window understates the gate.** The ellipse is drawn with χ²(p, 2) on the XY block, but the XY footprint of a 3-DOF gate is the same XY block with χ²(p, 3), so the drawn ellipse is about 11% too small. This adds to prob review 7 (wrong ellipse centre). Use the same df as matching.

**Z4 (Medium). `vz` is undamped and as noisy as horizontal velocity.** At production settings, `Q(vz)` adds 0.01 (m/s)² per 0.1 s.

- Noisy depth (stereo, LiDAR) produces a spurious `vz`, and `z` drifts during coasts.
- Because `isDynamic` now includes `vz`, that noise can switch a track between the static and dynamic coast timeouts.
- There is no way to pin `vz = 0` for ground-bound categories.
- **Fix:** give `vz` its own (smaller) noise as part of the per-model process noise in PR 3, or add a planar-category switch, and add a noisy-z coast test.

**Z5 (resolved). Tracker Service 3D detection input.** The z-axis version was dropped in favour of #2050, which reached this branch through main (E5). #2050 covers the gaps the z-axis version had: it adds `rotation`, requires a positive `size` with `translation`, and allows bbox-less detections. After the merge:

- `zMeasured` was missing on #2050's translation path, so `EuclideanBirth` always used XY in the Tracker Service; fixed in `9b2879806` (E5);
- the χ² df split is unchanged, and `vz` / `translation[2]` publishing is verified end to end with a climbing 3D detection.

**Z6 (Low). `zMeasured` is a proxy.** The Controller sets `zMeasured = 'translation' in info`, which is true for every child-scene and external-source object even when its z is a planar ground point. Birth clustering then uses XYZ for those objects. This is benign today; document it.

**Z7 (Low). Code hygiene.**

- **Fixed in `a0ea702b1`:** `chi2Cdf3` used `M_PI`; it now uses `std::numbers::pi`, as the C++20 change (`736c28e13`) did elsewhere.
- **Fixed in `a0ea702b1`:** `chi2Threshold(p, 3)` ran a 64-step bisection on every call, and the Controller calls it every frame (prob review 13). It now keeps the last result per thread. The cache is in C++ rather than Python so it cannot capture the test suite's `rv` mocks.
- Open: the 3×3 `S` assembly is duplicated in the dead `calculatePositionMahalanobisSquaredDistance` (prob review 16).
- Open: the near-singular guard (`|det| < 1e-12`) became `invert() == 0`, which only catches exactly singular matrices.

**Z8 (resolved). clang-format.** `make -C tracker lint-cpp` failed on 4 Tracker files, as it already did on `feat/tracking-z-axis`. All the violations were in the Tracker 3D-input changes that were dropped (Z5), so it is now clean.

**Z9 (Low). Docs.** These still describe a 2×2 / 2-DOF gate:

- `how-to-configure-tracker.md` (`gate_probability`: "2 DOF")
- the design doc and ADR-0017
- the `data_formats.md` description of the association window

`tracker/docs/implementation.md` now describes z tracking with 3D detections (`ac90ba78e`). The plan file section still refers to commit hashes from `feat/tracking-z-axis`.

**Z10. Test gaps.**

- All new filter tests use a single CV model; none runs production IMM {CV, CA, CTRV} with vertical motion.
- No test with pixel and 3D detections at different z references (Z1), no noisy-z coast test (Z4), and no test that the window df matches the gate (Z3).
- The functional `test_z_tracking.py` was not run.

## 4. Issues: PR extraction

**E1. Port.** Conflicts came from the base having moved on:

- `TrackingTests.cpp` was split by component, so the tests were relocated to `ObjectMatchingTests.cpp`, `MultiCameraFusionTests.cpp`, `MultipleObjectTrackerTests.cpp`, `MultiModelKalmanEstimatorTests.cpp` and a new `TrackedObjectTests.cpp`.
- `CoordinateTransformer` now undistorts two points (main #2018).
- `ObjectClassConfig` gained `rotation_from_velocity`.

Before the Tracker 3D input was dropped, the non-test diff matched the original apart from one hand-merged doc comment.

The Tracker 3D input was then removed (Z5):

- `ee97eacdb` is dropped entirely.
- `00aa9531c` keeps only the χ² df split and the publisher / config tests.
- `3c45aee55` loses its two Tracker translation-path lines.
- The plan file section was adjusted to match.

**E2 (fixed in `b0a2795dd`).** The filter tests added later on `feature/prob-tracking-extracted` hard-code the 12-state layout: `test::idx`, `kStateSize = 12`, and 12-element `P0` / `Q` diagonals. They compile against 13 states but test the wrong indices. `test::idx` now derives from `StateIndex`, the UKF reference transition adds `z += vz·dt`, and the `vz` entries of `P0` and `Q` are covered.

**E3. Association update (`ab0caa89c`, then `e61fb828c`; merged as #2103).** Conflict resolution:

- Streaming fusion is removed (#2061), so `matchAndAssignMeasurements` loses its `timestamp` argument and `kStreamingMultiCamHold` goes.
- `maxRadiusM` and the 2 m Euclidean birth radius stay.
- The benchmark drops its per-target C++ standard, now set at directory scope.
- The PR 4 tests move to the split files; the duplicate covariance-getter test and the streaming test are dropped.
- `TrackingWorker` keeps both `rotation_from_velocity_` and `association_config_`.
- `e61fb828c`: `scene_controller.py` keeps both `normalize_association_config` and `stripReidProvenance` imports.

**E5. Base update with Tracker 3D detections (`d20bb3775`, `9b2879806`, `ac90ba78e`).** Merging the association branch @ `1fd627aa2`, which includes #2050, had no text conflicts. Semantic check:

- **Fixed:** #2050's translation path left `zMeasured` false, so stacked-floor 3D detections from two cameras were fused into one track. `9b2879806` sets it; a new `TrackingWorker` test failed before the fix and passes after it.
- Covered by new tests: the pixel path keeps `zMeasured` false; a climbing 3D detection publishes `translation[2]` and `velocity[2]` (end to end through `TrackingWorker`).
- Compatible: published `velocity` now carries `vz` for both paths; #2050's rotation handling (identity unless orientation was observed, Kalman yaw vs velocity heading) is independent of z, and it resolves yaw review finding 1 for the Tracker Service.
- robot_vision is unchanged by the merge, so the filter results above still apply.

**E4. Failures that already exist on the association branch (not regressions).**

- `SingleJumpingDetectionTracking`.
- In full-suite pytest runs, 5 PR 4 tests (`test_ilabs_tracking` ×3, `test_scene_controller` ×2) fail because the session-scoped autouse fixture `mock_ilabs_rv` in `scene_pytest/conftest.py` leaves `controller.ilabs_tracking.rv` mocked. They pass in isolation. `make run_unit_tests` would hit this.
- 3 failures are environment-only (`node`, compose `.env`).
- `TimeChunkSchedulerTest.Dispatch_AppliesRotationFromVelocityPerCategory` failed once under load because of its 1 s wall-clock wait, then passed 5 of 5 runs.

## 5. Issues: future merge of `tdorau/imm-ukf-improvements` (#2056)

Simulated with throwaway merges, first with #2056 @ `a4e2d33fb` and then with its new head `2804edf78`, which adds per-model process noise.

**I1 (fixed in `e1292f438`, `671601473`). Association + #2056.** Only one trivial text conflict (benchmark SPDX line), but it does not compile:

- `.at<double>()` is called on members that become `cv::Matx`, in the `ObjectMatching.cpp` PositionMahalanobis cache and in `tracker/inc/association_window.hpp`.
- `ObjectMatchingTests.cpp` and `tracking_test.py::test_position_mahalanobis_prefers_motion_axis` use the removed `TrackManager::getTrack()` / `get_track`.
- PR 4's rewritten benchmark still fills the Kalman matrices through the `cv::Mat` API (#2056 removed that from the old benchmark), so it breaks once benchmarks are built.

The fixes are mechanical and belong to PR 4.

**I2. 3d + #2056.**

- Text conflicts:
  - `TrackedObject.hpp`: `StateSize` 13 vs 12. Take 13 together with #2056's `Matx` aliases.
  - `MultiModelKalmanEstimator.cpp` and its test: #2056 replaces `kinematicProcessNoiseCov` with a per-model `processNoiseCov(model, …)`.
  - The benchmark and `test/CMakeLists.txt` (test source list, re-checked with #2056 @ `181a851d4`): trivial.
- **#2056's new noise code hard-codes 12-state indices:** `Rect(2, 2)` and `Rect(4, 4)` for the velocity and acceleration blocks, `(10, 10)` for yaw and `(11, 11)` for yaw rate. Under the 13-state layout, yaw noise would land on height and yaw-rate noise on yaw. Resolve with `StateIndex`, and add `Q(VZ, VZ)` explicitly (Z4 decides its value per model). In the per-model test, add the `vz` entry to the cases and to the zeroed `rest`.
- **Guard applied in `0d0cf075f`:** without it, the header auto-merged silently to `StateSize = 12`, which compiles but fails at run time. `StateSize` is now `constexpr 13`, so that line conflicts visibly, and `static_assert`s tie `StateSize` / `MeasurementSize` to `StateIndex` / `MeasurementIndex`. Verified: the header now conflicts.

**I3. Trial results after these resolutions and the I1 mechanical fixes.**

- With #2056 @ `2804edf78` (3d @ `a0ea702b1`): robot_vision 68/68, including `SingleJumpingDetectionTracking`, which per-model process noise fixes; Tracker unit 501/501; Python not run.
- With #2056 @ `a4e2d33fb` (before the Tracker 3D input was dropped): robot_vision 60/61, Tracker unit 507/507, Python 166/167 (only the PR 4 `get_track` test).
- No behavioural conflict between the per-model predicted measurements / process noise and 3D gating.

**I4. Order.** Merge #2056 into `feature/prob-tracking-extracted`, propagate to association (fix I1 there), then to 3d (resolve I2).

**I5. Plan interplay.**

- PR 3 "process-noise floor on position, z and size": z already gets indirect noise through `vz`.
- PR 3 per-model process noise (now in #2056) and the `default_process_noise` docs must cover `vz` (Z4).
- PR 3 test tools (`Trajectory` / `TruthSample`) have no vertical motion, so climb scenarios cannot reuse them yet.
- PR 4 configurable birth radius now applies to `EuclideanBirth`.
- prob review 3 (unguarded `at<>` on an empty covariance) goes away with `Matx`.

## 6. Actions

| #   | Action                                                                              | Status                                                                                |
| --- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| 1   | `make -C tracker format-cpp` (Z8)                                                   | Not needed (Z8 resolved)                                                              |
| 2   | `StateSize` `constexpr 13` + `static_assert` (I2)                                   | Done, `0d0cf075f`                                                                     |
| 3   | `M_PI` → `std::numbers::pi`; cache the χ²(3) threshold (Z7)                         | Done, `a0ea702b1`                                                                     |
| 4   | Docs: 3-DOF gate (Z9)                                                               | Tracker doc done (`ac90ba78e`); Controller docs, design doc and ADR-0017: plan step 5 |
| 5   | Conditional z gating + per-pair df, window df that matches matching (Z1-Z3) + tests | Plan step 5                                                                           |
| 6   | Separate `vz` noise / planar categories (Z4)                                        | Plan step 5, with PR 3 per-model process noise                                        |
| 7   | Wildtrack + Unity evaluation vs association branch (Z2)                             | Plan step 5                                                                           |
| 8   | Fix the session-scoped `rv` mock leak (E4); prepare PR 4 for #2056 (I1)             | I1 done (`e1292f438`, `671601473`); E4: plan step 4                                   |
| 9   | Tracker 3D detection input, then `zMeasured` on its translation path (Z5)           | Done: #2050 + `9b2879806` (E5)                                                        |
