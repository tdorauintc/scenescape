# PR 1958 Review (`ITEP-96642: Enable point cloud visualization`)

The commit is c2a80ef3, "ITEP-96642: Enable point cloud visualization". It mostly does what ADR 0017 describes, but I found one likely regression, one place where the code behaves differently from what the ADR says, and a few smaller issues. I only read the code; I didn't build or run any tests.

## What changed, checked against the ADR

| ADR decision | Implementation | Matches? |
|---|---|---|
| Tag detections that carry a rotation with `has_orientation` | `to_rv_object` in `ilabs_tracking.py:170-178` | Yes |
| Cameras don't change yaw: measured yaw is set to the predicted yaw | `prepareYawMeasurement` in `OrientationAttributes.hpp:111-136` | Partly (finding 2) |
| Speed gate: flip yaw by π toward the direction of travel, drop it if still more than 0.6 rad off | Same function, the branch for speeds ≥ 1 m/s | Yes |
| When several sensors match one track in a frame, take yaw from the most confident orienting one | `applyOrientingYaw` in `MultipleObjectTracker.cpp:149-185` | Mostly (finding 6) |
| `orientation_observed` stays set on the track once any orienting sensor updates it | `mergeOrientationAttributes` plus `initialize()` | Yes |
| Mahalanobis association uses yaw only when both detection and track have orientation | `ObjectMatching.cpp:34-48` | Partly (finding 3) |
| Publish rules (Kalman yaw, or direction of travel if they disagree by more than 0.6 rad) | `from_tracked_object` in `ilabs_tracking.py:212-245` | Yes (finding 4) |
| Motion model: yaw now turns with the estimated turn rate | `CTRVModel.cpp:31-34` | **The ADR doesn't list this as a decision** |

The yaw math checks out. `rv::angleDifference(a, b)` returns `wrap(b − a)`, so `previousYaw − angleDifference(chosen, previousYaw)` correctly unwraps `chosen` near `previousYaw`.

## Findings, most serious first

**1. Likely regression in the separate tracker service.** The `tracker` service compiles this same library directly. It publishes `yawToQuaternion(rv_track.yaw)` in `tracking_worker.cpp:273`, and its detections always have yaw 0 and never set `has_orientation`.
- **Before:** every camera detection pulled yaw back to about 0, so published rotation stayed at identity.
- **Now:** camera detections no longer hold yaw in place, and the motion model keeps adding turn rate to it. Yaw ends up as "how much the object has turned since the track started", which isn't a real heading, and that is what gets published.
- The ADR doesn't mention the tracker service, and no tracker test checks rotation over time.
- **Fix:** in `convert_tracks`, publish identity unless the track has `orientation_observed`.

**2. "Let yaw predict" is not what the code does.** Setting the measured yaw equal to the predicted yaw still runs a full Kalman correction on yaw:
- **Yaw uncertainty shrinks** every camera frame, as if yaw had been measured. When LiDAR finally sees a camera-started track, its yaw gets very little weight. With the controller's noise settings (process noise 1e-4, measurement noise 0.2) the gain settles around 0.02 per frame, so it converges slowly. That contradicts the ADR's claim that LiDAR gives "smooth yaw corrects after camera-only predicts".
- **With three motion models, the yaw change isn't zero per model.** The fake measurement is the combined yaw, so each model's yaw gets pulled toward the average. That damps the new turn-rate yaw in the CTRV model, and the yaw difference also affects how the models are weighted against each other.
- **Fix:** do a real reduced update for detections without orientation: drop the yaw row and column from `Syy`/`Sxy` in `UnscentedKalmanFilterMod::correct`, or use a very large yaw noise for that update.

**3. The Mahalanobis yaw difference isn't wrapped.** `measurement.yaw` is a raw value in (−π, π]. The track's predicted yaw is unwrapped and can be off by π after the direction-of-travel flip. The difference can therefore come out near π or 2π, which blocks the match and splits the track.
- This is latent: both the controller and the tracker service currently use `DistanceType::Euclidean`.
- **Fix:** use `-rv::deltaTheta(measurement.yaw, predictedYaw)` as the difference. Ideally also apply the same speed gate, so yaw that the update step would drop doesn't affect matching either.

**4. The publish switch can flicker.** `_kalman_yaw_disagrees_with_velocity` uses one cutoff each for angle (0.6 rad) and speed (1 m/s), with no hysteresis. Near either cutoff, the published rotation can jump by 0.6 rad or more from frame to frame. The existing direction-of-travel logic uses separate on/off thresholds (1.0 / 0.5 m/s) for exactly this reason.
- Also, the fallback publishes direction of travel even in scenes where `rotation_from_velocity` is disabled. That's a behavior change; it may be intended, but it isn't documented.

**5. It assumes objects always move forward.** Both the C++ gate and the Python publish logic point the object's front along its direction of travel. A vehicle reversing at 1 m/s or more will be shown facing the wrong way. The ADR doesn't list this as a limitation.

**6. "Highest confidence" isn't really confidence.** The Python side builds the classification vector as `[c, 1−c]`, and `applyOrientingYaw` ranks by `maxCoeff()` ([line 165](controller/src/robot_vision/src/rv/tracking/MultipleObjectTracker.cpp#L165)). A detection with confidence 0.3 therefore beats one with 0.6. It should use the probability of the detected class instead.

**7. The thresholds are hardcoded twice.** 1.0 m/s and 0.6 rad are defined in both C++ (`MIN_SPEED_FOR_YAW_GATE`, `MAX_YAW_VELOCITY_RESIDUAL`) and Python (`SPEED_THRESHOLD_ON`, `YAW_VELOCITY_DISAGREE_RAD`). Nothing keeps them in sync and neither is configurable.

## Gaps in the ADR itself
- Its status is still `Proposed`, but the code is already merged.
- It describes CTRV integrating yaw as existing behavior, but this commit introduces that change. It should be listed under Decision.
- It doesn't mention the tracker service (finding 1), the reversing-vehicle limitation (finding 5), or that the "predict" wording doesn't match the update the code actually runs (finding 2).

## Gaps in tests
- No test covers Mahalanobis yaw matching, including the wrap bug.
- No test covers camera-only tracks with the new CTRV yaw: yaw should stay bounded, and the tracker service output should stay identity.
- No test checks that yaw uncertainty is unchanged after a camera-only update.
- No Python test covers the publish switch near its thresholds, or the case where `rotation_from_velocity=False` on a track that has had orientation.

## Existing bug, not from this commit
`UnscentedKalmanFilterMod::setStateAndCovariance` in `UnscentedKalmanFilter.hpp:120-124` does nothing, because its parameters have the same names as the members they're meant to set. As a result the three motion models never mix their states and each filter runs on its own. That makes finding 2 worse, and anyone reasoning about "the combined yaw" should know about it.
