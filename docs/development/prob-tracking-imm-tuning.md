<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Robot-vision IMM tuning

What can be tuned in the robot-vision IMM-UKF (`MultiModelKalmanEstimator`), how to measure it, and what affects what.
No values: they change with the code. Filter level only; association and track lifecycle are out of scope.

| Item            | Value                                                                                                                                                              |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Code references | `tdorau/imm-ukf-improvements` @ `2804edf78` (#2056, per-model process noise)                                                                                       |
| Related         | [test plan](prob-tracking-pr3-rv-tests-plan.md) (F-n, E-n), [post-review plan](prob-tracking-post-review-plan.md), [visualization plan](prob-tracking-viz-plan.md) |

## 1. Terms

| Term                                                      | Definition                                                                                                                                                                                                     | Code                                                              |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Motion model                                              | State transition a filter predicts with. CV resets acceleration and turn rate, CA resets turn rate, CTRV resets acceleration                                                                                   | [CV][cv], [CA][ca], [CTRV][ctrv]                                  |
| Nested models                                             | CA with zero acceleration and CTRV with zero turn rate predict exactly like CV                                                                                                                                 | as above                                                          |
| Manoeuvre state                                           | The state only one model keeps: CTRV's turn rate w, CA's acceleration a                                                                                                                                        | as above                                                          |
| Model probability μ_j                                     | Belief that the target moves like model j; the μ_j sum to 1                                                                                                                                                    | [`mModelProbability`][mu]                                         |
| Transition probability p_ij                               | Assumed probability that a target moving like model i moves like model j at the next predict. Fixed matrix, applied per predict (not per second), used only for mixing                                         | [matrix][transition]                                              |
| Mixing, mixing weight μ(i\|j)                             | At each predict every model starts from a blend of all models' states and covariances, weighted μ(i\|j) ∝ p_ij·μ_i                                                                                             | [`combiningProbability`][combining], [`interaction`][interaction] |
| Probability floor and ceiling                             | After the Bayes step every μ_j is rescaled linearly into [floor, ceiling]: no model leaves the range, and every update pulls all μ toward equal                                                                | [limits][limits], [rescale][rescale]                              |
| Prior                                                     | Transition probability and floor together: assumptions applied every frame, whatever the detections say                                                                                                        | –                                                                 |
| Measurement noise R (r)                                   | Assumed detection noise; also the initial variance of the measured states                                                                                                                                      | [R][r], [config][config]                                          |
| Process noise Q_j                                         | Per-model noise added at each predict: velocity along and across the motion, acceleration (CA), turn rate (CTRV), yaw, and a small floor on the states the model resets. Scaled from the process-noise setting | [`processNoiseCov`][q], [per predict][qpredict]                   |
| Initial covariance P0                                     | Initial variance of the latent states, capped by the initial-covariance setting                                                                                                                                | [initial P][p0]                                                   |
| Predicted measurement ẑ_j, innovation ν_j, covariance S_j | Model j's prediction of the next detection, the detection minus the prediction, and its covariance (projected P plus R)                                                                                        | [UKF correct][ukfcorrect], [S][s]                                 |
| Likelihood Λ_j                                            | N(ν_j; 0, S_j): how well model j predicted the detection. The update multiplies μ_j by Λ_j, then normalises and rescales                                                                                       | [log-likelihood and update][loglik]                               |
| Evidence                                                  | ln Λ_j − max over k≠j of ln Λ_k for one frame, in nats (1 nat multiplies the odds by e). Grows with (difference of the models' predictions)² / S. A diagnostic, not computed in the code                       | –                                                                 |
| Likelihood scale                                          | Absolute size of S. Scaling q, r and P0 together keeps each single filter's gains but scales the evidence                                                                                                      | –                                                                 |
| Camera yaw pseudo-measurement                             | A detection without orientation gets the track's combined yaw as its yaw measurement                                                                                                                           | [`prepareYawMeasurement`][yawprep]                                |
| Combined estimate                                         | μ-weighted mean and covariance of the models; what the tracker outputs                                                                                                                                         | [`combineStatesAndCovariances`][combine]                          |
| Association covariance                                    | S of the most probable model, used for gating                                                                                                                                                                  | [best model][assoc]                                               |
| Sigma-point parameters α, β, κ                            | UKF spread and weights of the sigma points                                                                                                                                                                     | [α, β][ukfparams], [κ][kappa]                                     |
| Published yaw                                             | Camera-only tracks publish the velocity heading. The Controller publishes the filter yaw once an orienting sensor was seen, unless it disagrees with the heading; the Tracker service never publishes it       | [Controller][pubctl], [Tracker][pubtrk]                           |

## 2. What is tuned

| Knob                                                                           | Where                                          | Acts on                                           |
| ------------------------------------------------------------------------------ | ---------------------------------------------- | ------------------------------------------------- |
| `default_measurement_noise` (r)                                                | tracker config, [production constants][config] | R, initial P of measured states, likelihood scale |
| `default_process_noise` (q)                                                    | tracker config, production constants           | Q of every model                                  |
| Q shape: velocity scale, cross-track ratio, turn-rate scale, yaw ratio, floors | [`processNoiseCov`][q]                         | Q per model                                       |
| `init_state_covariance` (P0)                                                   | tracker config, production constants           | initial latent variances                          |
| `motion_models`                                                                | tracker config, production constants           | which models compete                              |
| Transition probability, probability floor and ceiling                          | [matrix][transition], [limits][limits]         | prior                                             |
| α, β, κ                                                                        | [constructor][ukfparams]                       | sigma points                                      |

## 3. How it is measured

Scenario tests drive one estimator with [`FilterRun`][filterrun] (no association), with truth from [`Trajectory`][trajectory] and a seeded [`Sensor`][sensor], in the production config.
Run several seeds and sensor noise levels. The recorder and plots of the [visualization plan](prob-tracking-viz-plan.md) show the time series behind each number.

| KPI                | Definition                                                                                                                                            | Test                                                                                                |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Differentiation    | Mean μ of the expected model over a steady manoeuvre window, and its margin over the runner-up                                                        | [`ModelSelection`][t-sel]                                                                           |
| Onset latency      | Time from manoeuvre start until the expected model leads for a few consecutive frames                                                                 | not yet                                                                                             |
| Release            | After a manoeuvre: time until its manoeuvre state decays, and the position error in the following window. Not the time until CV leads (nested models) | not yet                                                                                             |
| Evidence           | Mean evidence per frame of the expected model in a window; explains the two rows above                                                                | not yet                                                                                             |
| Accuracy           | Maximum and rms position error after warm-up, final speed error, mean along- and cross-track offset                                                   | [`TracksMotionCases`][t-cases]; offsets: [steady motion][t-offset], [turns][t-circle] (known issue) |
| Turn-rate learning | CTRV's own w, not the diluted combined w                                                                                                              | [`TurningTargetLearnsTurnRate`][t-w]                                                                |
| Yaw                | Filter yaw against the heading: camera-only, orienting sensor, and published yaw of orienting-then-camera tracks                                      | [turning heading][t-yaw], [rotation in place][t-rot]                                                |
| Smoothness         | Straight-line rms relative to a CV-only filter; jitter as rms of the estimate's second difference                                                     | [`StraightLineMatchesConstantVelocityFilter`][t-straight]                                           |
| Coasting           | Position error after predicts without detections                                                                                                      | [`CoastingAfterTurn`][t-coast]                                                                      |
| Consistency        | Every model covariance positive definite; behaviour with detections noisier than r, alternating camera bias, jumps                                    | [`CovarianceStaysPositiveDefinite`][t-pd]                                                           |
| Speed acquisition  | Speed of a target born moving; constant-velocity convergence                                                                                          | [`TargetBornMovingAcquiresSpeed`][t-born]                                                           |

- Scenario coverage: turn evidence grows with speed × turn rate, so cover walkers and slow and fast cars, short corners, sustained circles, braking and stops, and orienting-then-camera sequences.
- End-to-end runs (Unity, Wildtrack: HOTA, DIST_T, rms_jerk, acceleration_variance) confirm a change but do not localise its cause.

## 4. Trade-offs and relationships

Two axes:

- **Prior** (transition probability, floor) sets how much every frame pulls the μ back. Stickier: clearer μ and kept manoeuvre states, but a wrong model's state lingers. Looser: faster release, flatter μ. Changing it moves along one trade-off curve.
- **Evidence** (likelihood) sharper: faster onset, clearer μ and faster release together. It moves the curve.
- Steady μ and switching speed are the balance between evidence per frame and pull-back per frame. With weak evidence, every prior change looks like a trade-off.

What affects what:

- q/r ratio → single-filter bandwidth: lag in manoeuvres against jitter and straight-line error.
- q, r and P0 scaled together → S → evidence, with smoothing unchanged. r below the real detection noise → overconfident filter: jitter, false manoeuvres, a narrower association gate.
- Cross-track velocity noise (and CA's sideways acceleration noise) → CV and CA follow short corners with less lag, but take turns from CTRV, so its w and the camera-only yaw stop following.
- CV's along-track velocity noise → CV tolerates acceleration → less evidence for CA.
- CA acceleration noise → faster braking and acceleration following, against turns absorbed as acceleration and deceleration kept after a stop.
- CTRV turn-rate noise → faster turn-rate learning and turn exit, against a wider sideways S, wobble on straight lines and coasting spread. A target property: it should not scale with r.
- Yaw noise → orienting-yaw responsiveness against camera-only yaw drift.
- Reset-state floor → keeps covariances positive definite; no tuning effect while small.
- P0 → speed acquisition at birth against early overshoot.
- Mixing dilution: each predict scales a model's manoeuvre state by its self-mixing weight. A low μ erases it, which lowers that model's evidence and μ further. Whatever lowers CTRV's μ also lowers its w and the camera-only yaw.
- Camera yaw pseudo-measurement → penalises CTRV for turning its yaw; the penalty grows as r shrinks.
- Nested models → no evidence on steady straight motion; CV's μ there is not a KPI.
- Frame rate → the transition probability acts per predict, process noise per second: the effective prior changes with the frame rate.
- Association covariance → every noise change also changes gating (PR 4).
- Multiple cameras → Controller Immediate mode alternates camera biases, which look like noise; time-chunking averages them.
- κ → predicted mean under strong nonlinearity (CTRV with an uncertain w, long predicts) → coasting.

## 5. Prerequisites before tuning

1. F-2: detections without orientation give no yaw measurement. Removes the yaw penalty from the model likelihoods, which otherwise grows as r shrinks.
2. Separate noise roles: r as a measured sensor property per deployment; velocity, acceleration and turn-rate noise as target dynamics, not on r's scale. Document their meaning (prob review 4).
3. Measure the detection noise per deployment after projection: random part and slowly varying bias, per camera. Unity's ground-truth boxes are not representative.
4. Transition probability per unit time, derived from Δt.
5. One prior mechanism: decide between the linear floor rescale and Markov-predicted model probabilities (baseline 9.2).
6. F-6 (Cholesky failure handling) and F-5 (position and size noise floor), so sharper settings cannot silently break covariances.
7. Robustness to jumps: disagreeing models mixed with a small S diverge (`SingleJumpingDetectionTracking`); a smaller S makes this likelier.
8. E-1 (sigma-point weights) before tuning the turn-rate noise.
9. KPI tooling in `test/support`: onset and release latency, evidence, per-model states in the recorder, and the scenario set of section 3.
10. Re-evaluate the association gate (PR 4) after every noise change.

[cv]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/CVModel.cpp#L9-L38
[ca]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/CAModel.cpp#L9-L41
[ctrv]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/CTRVModel.cpp#L9-L63
[mu]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/include/rv/tracking/MultiModelKalmanEstimator.hpp#L185-L186
[transition]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L81-L85
[combining]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L401-L423
[interaction]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L425-L460
[limits]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L74-L75
[rescale]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L538-L545
[r]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L109
[config]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/include/rv/tracking/TrackManager.hpp#L18-L41
[q]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L125-L182
[qpredict]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L264-L268
[p0]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L87-L101
[ukfcorrect]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/UnscentedKalmanFilter.cpp#L189-L212
[s]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/UnscentedKalmanFilter.cpp#L224-L227
[loglik]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L519-L545
[yawprep]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/include/rv/tracking/OrientationAttributes.hpp#L111-L116
[combine]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L548-L571
[assoc]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L313-L328
[ukfparams]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/include/rv/tracking/MultiModelKalmanEstimator.hpp#L29
[kappa]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L35
[pubctl]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/controller/ilabs_tracking.py#L210-L242
[pubtrk]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/tracker/src/tracking_worker.cpp#L95-L107
[filterrun]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/test/support/Scenario.hpp#L219
[trajectory]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/test/support/Scenario.hpp#L58
[sensor]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/test/support/Scenario.hpp#L174
[t-sel]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/test/MotionScenarioTests.cpp#L208
[t-cases]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/test/MotionScenarioTests.cpp#L143
[t-w]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/test/MotionScenarioTests.cpp#L267
[t-yaw]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/test/MotionScenarioTests.cpp#L324
[t-rot]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/test/MotionScenarioTests.cpp#L352
[t-straight]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/test/MotionScenarioTests.cpp#L365
[t-coast]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/test/MotionScenarioTests.cpp#L307
[t-pd]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/test/MotionScenarioTests.cpp#L240
[t-born]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/test/MotionScenarioTests.cpp#L415
[t-offset]: https://github.com/open-edge-platform/scenescape/blob/5ccd64279330261727255b38d6738a3304a6f077/controller/src/robot_vision/test/MotionScenarioTests.cpp#L512
[t-circle]: https://github.com/open-edge-platform/scenescape/blob/5ccd64279330261727255b38d6738a3304a6f077/controller/src/robot_vision/test/MotionScenarioTests.cpp#L602
