# `feature/prob-tracking` branch split plan

This is the plan to split the `feature/prob-tracking` branch, so we can proceed granularly and carefully evaluate impact on accuracy and performance for each of them.

References like "yaw review 6" or "yaw review E2" point to findings in [pr-review-yaw-fusion.md](pr-review-yaw-fusion.md).
References like "prob review 2" or "prob review G9" point to issues and coverage gaps in [pr-review-probabilistic-tracking.md](pr-review-probabilistic-tracking.md).
References like "delta 9.1" point to Section 9 items in [robot-vision-tracking-prob-tracking-delta.md](robot-vision-tracking-prob-tracking-delta.md).
References like "baseline 9.4" point to Section 9 items in [robot-vision-tracking-algorithms.md](robot-vision-tracking-algorithms.md).

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

2. **[IN REVIEW]** Multicamera geometry fusion. Branch multi-camera-geometry-fusion. Base branch: main
   - Carried over from feature/prob-tracking
     - multicamera geometry fusion (time-chunking, streaming, birth clustering with configured distanceThreshold)
     - required supporting changes in Controller
   - My proposed additions:
     - fixes
       - unequal weights for birth clustering + UT
       - removing measurements after using in streaming average
       - enable running robot-vision UT in CI
     - related evaluation / additional testing
       - increase coverage for streaming and fuseGeometry (dynamic objects, more than 2 cameras, test all averaged values, edge cases)
       - verify that fuse streaming improves, if yes - tune kStreamingMultiCamHold or make it configurable / adaptive
       - Evaluate and document impact
       - verify performance impact of streaming fusion in robot-vision benchmark (by extending robot vision benchmark with multicamera scenario on a temporary evaluation branch)
         - temporary branch name: `tdorau/tmp-rv-benchmark-multicamera`
         - added on top of original `feature/prob-tracking` benchmark:
           - separate overlap / non-overlap mode
           - separate immediate / time-chunking tracker scenarios
           - People who keep walking from frame to frame, and detections without Kalman matrices. PR 4 still drew new random people every frame.
           - parameter `--distance-threshold` (Euclidean only), replacing `--association-config`.

Both branches 1 and 2 should be merged to a new feature branch `feature/prob-tracking-extracted` (see below) through main before the final evaluation.

## What to extract into a new PR and merge first into a new feature branch (keeping the order), then to main:

3. **[IN-PROGRESS]** IMM-UKF changes. Branch: feature/prob-tracking-extracted. Base branch: multi-camera-geometry-fusion
   - Carried over from feature/prob-tracking
     - Fixing IMM S_pred and mixing, process-noise redesign and the new initial uncertainty (MultiModelKalmanEstimator.cpp)
     - Fixing UKF (UnscentedKalmanFilter.cpp)
   - My proposed additions:
     - Introduce per-model process noise, including yaw and yaw rate so that CTRV learns the turn rate (yaw review E3)
     - Treat detections without orientation as having no yaw measurement (reduced update in `UnscentedKalmanFilterMod::correct`, or a very large yaw noise) instead of a zero-innovation update; update the "predict" wording in the selective-yaw ADR (yaw review 2)
     - Give each motion model its own predicted-measurement buffer in `MultiModelKalmanEstimator::initialize()`; PR 4's Mahalanobis gate is centred on this mean (yaw review E2)
     - Extend the tests coverage to include more motion models (manoeuvring motion, sudden stops)
     - Extend the tests coverage to include {CV, CA, CTRV} models set (exercise predictState(), not only singleModelPredict()).
     - Extend the tests coverage for yaw: yaw uncertainty unchanged after a camera-only update, LiDAR yaw responsiveness after a camera-only period, camera-only CTRV yaw stays bounded with mixing enabled, a turning target learns the turn rate, per-model predicted measurements differ (yaw review 2, E1-E3)
     - [moved from PR 2] yaw thresholding when unreliable + UT
     - [moved from PR 2] rank orienting yaw in `applyOrientingYaw` by the detected-class probability instead of `maxCoeff()` of `[c, 1-c]` + UT (yaw review 6)
     - Fixes for issues from the `feature/prob-tracking` review:
       - Add a small process-noise floor on position, z and size so their covariance does not collapse on long-lived tracks; add a long-duration test checking that the size gain stays non-zero and `errorCov` stays positive definite (prob review 2, G9; delta 9.1)
       - Document the new meaning of `default_process_noise` (x1000 velocity scaling, 1e-3 floor, no position/size noise) and `init_state_covariance` (cap on latent states only, measured states use `measurement_noise`) in `how-to-configure-tracker.md` (prob review 4)
       - Explain or revert the velocity tolerance loosening (0.01 -> 0.05) in `tracking_test.py` (prob review 5)
       - Add direct UT for `kinematicProcessNoiseCov` (near-zero velocity fallback, diagonal motion, dt scaling, `qVel` floor), for the initial covariance caps, and for re-initialisation not duplicating filters (prob review G8, G14)
       - Measure speed acquisition for a target that is born already moving fast; if it lags, revisit the 0.05 velocity prior cap (delta 9.2)
     - Handle a failed Cholesky factorisation in `UnscentedKalmanFilterMod::getSigmaPoints`: its result is ignored today, so sigma points are silently built from a partly factorised matrix. On failure symmetrize the covariance, add diagonal jitter and retry, log once; UT with a non-positive-definite covariance (baseline 9.4)
     - Evaluate the sigma-point weights (kappa = 3 - n gives centre weights -3 for the mean and -1 for the covariance) against kappa = 0 after per-model process noise. With beta = 2 they cannot break positive definiteness, but they extrapolate the CTRV predicted mean under strong nonlinearity (multi-step coasts with uncertain turn rate, single long predicts after reactivating a suspended track). Keep and document, or change + UT (baseline 9.4, delta 9.10)
     - Build robot-vision as strict C++20 everywhere + CI (`tracker-service.yml`) building the Controller image when `controller/src/robot_vision/**` changes

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

5. **[TODO]** Dataset and testing. Base branch: feature/prob-tracking-extracted-association. To be merged finally to main
   - Final accuracy and performance evaluation

## Parallel efforts

1. **[TODO]** Adopting a dataset with more diverse motion models in Tracker Evaluation (cars), to be merged into feature branch `feature/prob-tracking-extracted` for final evaluation.
