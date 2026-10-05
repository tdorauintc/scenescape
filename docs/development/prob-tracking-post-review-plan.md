# `feature/prob-tracking` branch split plan

This is the plan to split the `feature/prob-tracking` branch, so we can proceed granularly and carefully evaluate impact on accuracy and performance for each of them.

References like "yaw review 6" or "yaw review E2" point to findings in [pr-review-yaw-fusion.md](pr-review-yaw-fusion.md).

## What to extract into a new PRs to main branch:

1. Tracker shift projection + related evaluation update. Branch: tracker-eval-projection-shift. Base branch: main
  - Carried over from feature/prob-tracking
    - Tracker Evaluation pipeline change (to accept object class configuration)
    - Tracker Service - narrowed down to object-class and shift projection (w/o new association config)
    - Unrelated fixes not covered by any other branch:
      - CONTRIBUTING.md: license link `LICENSE` -> `LICENSES/Apache-2.0.txt`
      - docs/design/mlops-integration-reuse.md: `user_scripts/gvapython/sscape/` links -> `user_scripts/gstplugins/` + prettier table alignment
      - tools/tracker/evaluation/README.md and Agents.md: references to nonexistent `controller_evaluation.yaml` / `metric_test_evaluation.yaml` -> `pipeline_configs/black_box_unity/` and `black_box_wildtrack/`
      - Whitespace-only formatting: TrackManager.hpp, CameraUtils.cpp, MetadataFusionTests.cpp (EOF newline), TrackingTests.cpp (`MultipleDetectionTrackingStressTest` loop)
  - My proposed additions:
    - Doc updates
    - Evaluate and document impact

2. Multicamera geometry fusion. Branch multi-camera-geometry-fusion. Base branch: main
  - Carried over from feature/prob-tracking
    - multicamera geometry fusion (time-chunking, streaming, birth clustering with configured distanceThreshold)
    - required supporting changes in Controller
  - My proposed additions:
    - fixes
      - unequal weights for birth clustering + UT
      - yaw thresholding when unreliable + UT
      - rank orienting yaw in `applyOrientingYaw` by the detected-class probability instead of `maxCoeff()` of `[c, 1-c]` + UT (yaw review 6)
      - removing measurements after using in streaming average
      - enable running robot-vision UT in CI
    - related evaluation / additional testing
      - increase coverage for streaming and fuseGeometry (dynamic objects, more than 2 cameras, test all averaged values, edge cases)
      - verify that fuse streaming improves, if yes - tune kStreamingMultiCamHold or make it configurable / adaptive
      - Evaluate and document impact
      - verify performance impact of streaming fusion in robot-vision benchmark (by extending robot vision benchmark with multicamera scenario on a temporary evaluation branch)

Both branches 1 and 2 should be merged to a new feature branch `feature/prob-tracking-extracted` (see below) through main before the final evaluation.

## What to extract into a new PR and merge first into a new feature branch (keeping the order), then to main:

3. IMM-UKF changes. Branch: feature/prob-tracking-extracted. Base branch: multi-camera-geometry-fusion
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

4. Mahalanobis association. Branch: feature/prob-tracking-extracted-association. Base branch: feature/prob-tracking-extracted
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

5. Dataset and testing. Base branch: feature/prob-tracking-extracted-association. To be merged finally to main
  - Final accuracy and performance evaluation

## Parallel efforts

1. Adopting a dataset with more diverse motion models in Tracker Evaluation (cars), to be merged into feature branch `feature/prob-tracking-extracted` for final evaluation.
