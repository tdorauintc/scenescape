# `feature/prob-tracking` branch split plan

This is the plan to split the `feature/prob-tracking` branch, so we can proceed granularly and carefully evaluate impact on accuracy and performance for each of them.

References like "yaw review 6" or "yaw review E2" point to findings in [pr-review-yaw-fusion.md](pr-review-yaw-fusion.md).
References like "prob review 2" or "prob review G9" point to issues and coverage gaps in [pr-review-probabilistic-tracking.md](pr-review-probabilistic-tracking.md).
References like "delta 9.1" point to Section 9 items in [robot-vision-tracking-prob-tracking-delta.md](robot-vision-tracking-prob-tracking-delta.md).
References like "baseline 9.4" point to Section 9 items in [robot-vision-tracking-algorithms.md](robot-vision-tracking-algorithms.md).
References like "z review Z1" or "z review I2" point to findings in [pr-review-tracking-z-axis.md](pr-review-tracking-z-axis.md).

## What to extract into a new PRs to main branch:

1. **[DONE]** ~~Tracker shift projection + related evaluation update. Branch: tracker-eval-projection-shift. Base branch: main~~
   - Carried over from feature/prob-tracking
     - Tracker Evaluation pipeline change (to accept object class configuration)
     - Tracker Service - narrowed down to object-class and shift projection (w/o new association config)
     - Unrelated fixes not covered by any other branch:
       - CONTRIBUTING.md: license link `LICENSE` -> `LICENSES/Apache-2.0.txt`
       - docs/design/mlops-integration-reuse.md: `user_scripts/gvapython/sscape/` links -> `user_scripts/gstplugins/` + prettier table alignment
       - tools/tracker/evaluation/README.md and Agents.md: references to nonexistent `controller_evaluation.yaml` / `metric_test_evaluation.yaml` -> `pipeline_configs/ black_box_unity/` and `black_box_wildtrack/`
       - Whitespace-only formatting: TrackManager.hpp, CameraUtils.cpp, MetadataFusionTests.cpp (EOF newline), TrackingTests.cpp (`MultipleDetectionTrackingStressTest` loop)
   - My proposed additions:
     - Doc updates
     - Evaluate and document impact

2. **[DONE]** ~~Multicamera geometry fusion. Branch multi-camera-geometry-fusion. Base branch: main~~ Merged to main as #2028 (`feaf1d6d5`, squash), without streaming fusion
   - Carried over from feature/prob-tracking
     - multicamera geometry fusion (time-chunking, birth clustering with configured distanceThreshold)
   - My proposed additions:
     - fixes
       - unequal weights for birth clustering + UT
       - enable running robot-vision UT in CI
     - related evaluation / additional testing
       - increase coverage for fuseGeometry (dynamic objects, more than 2 cameras, test all averaged values, edge cases)
       - Evaluate and document impact
       - verify performance impact of streaming fusion in robot-vision benchmark (by extending robot vision benchmark with multicamera scenario on a temporary evaluation branch). Result: about 1% of Immediate-mode `track()` time, see the streaming fusion removal below
         - temporary branch name: `tdorau/tmp-rv-benchmark-multicamera`
         - added on top of original `feature/prob-tracking` benchmark:
           - separate overlap / non-overlap mode
           - separate immediate / time-chunking tracker scenarios
           - People who keep walking from frame to frame, and detections without Kalman matrices. PR 4 still drew new random people every frame.
           - parameter `--distance-threshold` (Euclidean only), replacing `--association-config`.
   - Streaming (Controller Immediate mode) fusion removed after review ([discussion](https://github.com/open-edge-platform/scenescape/pull/2028#discussion_r4232521428)). #2061 (branch tdorau/remove-streaming-fusion), merged into multi-camera-geometry-fusion before #2028
     - Removed: the 250 ms per-camera measurement cache (`kStreamingMultiCamHold`) and the Controller `camera_id` attribute that keyed it. Immediate mode is identical to main again
     - Reason: it adds a second smoothing layer on top of the Kalman filter, and the Controller is going to be deprecated (Tracker Service uses only time-chunking)
     - Impact of the removal (Controller Immediate, 3 interleaved runs): Unity HOTA +0.002, DIST_T_mean −5 mm, but rms_jerk +154% and acceleration_variance +390%; Wildtrack within noise except IDF1 −0.014. Time-chunking and Tracker Service within noise. Immediate-mode `track()` about 1% faster in the multi-camera robot-vision benchmark
     - No longer needed: removing measurements after use in the streaming average, tuning `kStreamingMultiCamHold`, streaming test coverage

Both branches 1 and 2 are in main; `feature/prob-tracking-extracted` merged main after #2028 (`703566358`).

## What to extract into a new PR and merge first into a new feature branch (keeping the order), then to main:

3. **[IN-PROGRESS]** IMM-UKF changes. Branch: feature/prob-tracking-extracted. Base branch: main (multi-camera-geometry-fusion until #2028)
   - Carried over from feature/prob-tracking
     - Fixing IMM S_pred and mixing, process-noise redesign and the new initial uncertainty (MultiModelKalmanEstimator.cpp)
     - Fixing UKF (UnscentedKalmanFilter.cpp)
   - My proposed additions:
     - **[DONE in #2056]** Introduce per-model process noise, including yaw and yaw rate so that CTRV learns the turn rate (yaw review E3, delta 9.8): each model's Q follows its own mixed velocity; CA adds acceleration noise, CTRV turn-rate noise. CTRV now wins car turns (probability 0.18 → 0.57) and learns the turn rate (0 → 0.38 rad/s); Unity HOTA +0.004 and DIST_T −5 to −7 mm in all three configurations; `track()` +1.6 % in the robot-vision benchmark
     - Treat detections without orientation as having no yaw measurement (reduced update in `UnscentedKalmanFilterMod::correct`, or a very large yaw noise) instead of a zero-innovation update; update the "predict" wording in the selective-yaw ADR (yaw review 2)
     - **[DONE in #2056]** Give each motion model its own predicted measurement: `TrackedObject` matrices are fixed-size `cv::Matx`, so copies own their data; `MultiModelKalmanEstimator` is move-only; unused `TrackManager::getTrack()` / `getKalmanEstimator()` and their Python bindings removed. PR 4's Mahalanobis gate is centred on this mean (yaw review E2)
     - **[DONE]** Extend the tests coverage to include more motion models (manoeuvring motion, sudden stops)
     - Extend the tests coverage to include {CV, CA, CTRV} models set (exercise predictState(), not only singleModelPredict()).
     - Extend the tests coverage for yaw: yaw uncertainty unchanged after a camera-only update, LiDAR yaw responsiveness after a camera-only period, camera-only CTRV yaw stays bounded with mixing enabled, a turning target learns the turn rate, per-model predicted measurements differ (yaw review 2, E1-E3)
     - [moved from PR 2] yaw thresholding when unreliable + UT
     - [moved from PR 2] rank orienting yaw in `applyOrientingYaw` by the detected-class probability instead of `maxCoeff()` of `[c, 1-c]` + UT (yaw review 6)
     - Fixes for issues from the `feature/prob-tracking` review:
       - Add a small process-noise floor on position, z and size so their covariance does not collapse on long-lived tracks; add a long-duration test checking that the size gain stays non-zero and `errorCov` stays positive definite (prob review 2, G9; delta 9.1)
       - Document the new meaning of `default_process_noise` (x1000 velocity scaling, 1e-3 floor, no position/size noise) and `init_state_covariance` (cap on latent states only, measured states use `measurement_noise`) in `how-to-configure-tracker.md` (prob review 4)
       - Explain or revert the velocity tolerance loosening (0.01 -> 0.05) in `tracking_test.py` (prob review 5)
       - Add direct UT for `kinematicProcessNoiseCov` (now `processNoiseCov`) (near-zero velocity fallback, diagonal motion, dt scaling, `qVel` floor), for the initial covariance caps, and for re-initialisation not duplicating filters (prob review G8, G14)
       - Measure speed acquisition for a target that is born already moving fast; if it lags, revisit the 0.05 velocity prior cap (delta 9.2)
     - Handle a failed Cholesky factorisation in `UnscentedKalmanFilterMod::getSigmaPoints`: its result is ignored today, so sigma points are silently built from a partly factorised matrix. On failure symmetrize the covariance, add diagonal jitter and retry, log once; UT with a non-positive-definite covariance (baseline 9.4)
     - Evaluate the sigma-point weights (kappa = 3 - n gives centre weights -3 for the mean and -1 for the covariance) against kappa = 0 after per-model process noise. With beta = 2 they cannot break positive definiteness, but they extrapolate the CTRV predicted mean under strong nonlinearity (multi-step coasts with uncertain turn rate, single long predicts after reactivating a suspended track). Keep and document, or change + UT (baseline 9.4, delta 9.10)
     - Re-evaluate Controller Immediate-mode jitter (rms_jerk, acceleration_variance) after the IMM-UKF changes, and find what in the filter achieves the jitter reduction the removed streaming fusion gave, without double smoothing (PR 2 review). After per-model process noise (Unity, 3 interleaved pairs): Immediate rms_jerk +6 %, acceleration_variance +16 % (within run-to-run noise); Controller time-chunking +39 % / +79 %, Tracker Service −15 % / −22 %
     - **[DONE]** Build robot-vision as strict C++20 everywhere + CI (`tracker-service.yml`) building the Controller image when `controller/src/robot_vision/**` changes

4. **[TODO]** Mahalanobis association. Branch: feature/prob-tracking-extracted-association. Base branch: feature/prob-tracking-extracted
   - Carried over from feature/prob-tracking
     - New association implementation (ObjectMatching.cpp + any other changes required to support it)
     - Required supporting changes in Controller and Tracker Service to pass down association config and produce association window
     - Update Tracker Evaluation pipeline with new association configs
     - Manager UI support for association window
     - Related documentation
     - Robot-vision benchmark fix & update
     - Apply fixed radius in birth clustering
   - My proposed additions / fixes:
     - Extend the tests coverage
     - Evaluate using mixed convariance for matching instead of picking best model, then decide
     - Evaluate / mitigate performance impact of numpy.linalg.eigh / cv::eigen on association window publishing
     - Make the fixed radius in birth clustering (kDefaultBirthClusterRadiusM) configurable
     - Wrap the yaw difference in the legacy `Mahalanobis` cost (`-rv::deltaTheta(measurement.yaw, predictedYaw)`) and apply the same speed gate as `prepareYawMeasurement` + UT including the ±π wrap (yaw review 3)
     - **[IN-PROGRESS]** Update with `feature/prob-tracking-extracted`: streaming fusion removal, C++20, tests split by component. Merge `ab0caa89c` pushed as `tdorau/prob-tracking-extracted-association-update`, waiting for a PR (z review E3)
     - Fix the session-scoped `controller.ilabs_tracking.rv` mock in `scene_pytest/conftest.py`: 5 association tests fail in full-suite pytest runs (z review E4)
     - Prepare for #2056: `cv::Matx` covariance access in `ObjectMatching.cpp` and `association_window.hpp`, removed `TrackManager::getTrack()` in the C++ and Python tests, Kalman matrices in the benchmark harness (z review I1)

5. **[IN-PROGRESS]** Non-planar Z / `vz` tracking. Branch: feature/prob-tracking-extracted-3d (work branch `tdorau/prob-tracking-extracted-3d` until the feature branch exists). Base branch: feature/prob-tracking-extracted-association
   - Carried over from `feat/tracking-z-axis` (based on an older association branch)
     - `vz` in the UKF state (13 states, named `StateIndex` / `MeasurementIndex`), integrated by CV / CA / CTRV
     - XYZ association: Euclidean and `PositionMahalanobis` (3×3, χ² df 3); the UI association window keeps χ² df 2
     - Hybrid `EuclideanBirth` birth clustering: XY unless both detections have measured z
     - Controller and Tracker Service publish `vz`; Tracker Service χ² df 3 / df 2 split
     - Unit tests (robot_vision, Controller, Tracker Service) and functional `test_z_tracking.py`
     - Not carried over: Tracker Service 3D detection input (`translation` / `size`), see step 6
   - My proposed additions / fixes:
     - **[DONE]** Adapt the filter tests from PR 3 to the 13-state layout (z review E2)
     - **[DONE]** `StateSize` as `constexpr` checked against `StateIndex`, so merging #2056 (`StateSize = 12`) conflicts visibly (z review I2)
     - **[DONE]** `std::numbers::pi` and cached χ²(3) threshold (z review Z7)
     - Gate z only when both the detection and the track have measured z (sticky track flag, like `orientation_observed`), χ² df per pair, and one z reference point for planar and 3D detections + UT with mixed sources (z review Z1, Z2)
     - Draw the association window with the same df as matching (z review Z3)
     - `vz` process noise per model in #2056's `processNoiseCov` (smaller than the horizontal one), or `vz` pinned for ground-bound categories + noisy-z coast UT (z review Z4)
     - Docs: 3-DOF gate in `how-to-configure-tracker.md`, design doc, ADR-0017 and `data_formats.md` (z review Z9)
     - Extend the tests coverage: production IMM with vertical motion, mixed planar / 3D association; run `test_z_tracking.py` (z review Z10)
     - Evaluate and document impact (Wildtrack, Unity) against the association branch (z review Z2)
     - After #2056 reaches the association branch: keep `StateSize = 13`, move #2056's `processNoiseCov` to `StateIndex` and add `Q(vz)` (z review I2)

6. **[TODO]** Tracker Service 3D detection input. Branch: ITEP-97104_tracker_3d_detections. Base branch: main, reaches the feature branches through main merges
   - Detection `translation` / `size` / `rotation` and detections without a pixel bounding box; replaces the Tracker Service input changes of `feat/tracking-z-axis`
   - Follow-up in feature/prob-tracking-extracted-3d once it arrives: set `zMeasured` on the translation path, check the χ² df split and `vz` publishing with 3D detections (z review Z5)

7. **[TODO]** Dataset and testing. Base branch: feature/prob-tracking-extracted-3d. To be merged finally to main
   - Final accuracy and performance evaluation

## Parallel efforts

1. **[TODO]** Adopting a dataset with more diverse motion models in Tracker Evaluation (cars), to be merged into feature branch `feature/prob-tracking-extracted` for final evaluation.
