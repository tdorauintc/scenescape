<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Robot-vision IMM tuning

## High level details

- Branch: none yet; tuning changes land in [PR 8](prob-tracking-post-review-plan.md#pr-8-dataset-and-testing) of the post-review plan (base `feature/prob-tracking-extracted-3d`).
- PR: none yet.
- Commit: code links point to `tdorau/imm-ukf-improvements` @ `2804edf78` (#2056, per-model process noise); links for definitions changed since (reduced yaw update, initial covariance, published yaw) point to `feature/prob-tracking-extracted` @ `8a315d93c`. PR 3 is on `main` since `3f0814c6f` (#2036); both commits stay reachable through their PRs.
- What can be tuned in the robot-vision IMM-UKF (`MultiModelKalmanEstimator`), how to measure it, what affects what, and what must be in place before tuning.

### Context

- No values: they change with the code. Filter level only; association and track lifecycle are out of scope, but every noise change also changes the association gate, so re-evaluate PR 4's association after each one.
- The tuning items (yaw variance growth, initial velocity variance 1 → 16, size noise floor, velocity smoothing, Immediate-mode jitter, turn offset) and the pinned test bounds are in [PR 8](prob-tracking-post-review-plan.md#pr-8-dataset-and-testing) of the post-review plan; this plan holds the tuning knowledge and the prerequisites. Both plans are the single source of truth.
- Terms, knobs, KPIs and trade-offs: [Details / Context](#context-1).
- F-n, E-n, "prob review N" and "baseline 9.N" identify findings in the deprecated documents, for back-tracking only.

### Related documents

- [Post-review plan](prob-tracking-post-review-plan.md): PR 3 (done filter fixes) and PR 8 (tuning items, pinned test bounds); single source of truth with this plan.
- [PR 3 test plan](../deprecated/prob-tracking-pr3-rv-tests-plan.md) (deprecated): F-n and E-n mechanisms and measurements.
- [Visualization plan](../deprecated/prob-tracking-viz-plan.md) (deprecated): recorder and plot design; workflow in `tools/tracker/evaluation/visualization/README.md`.
- [baseline](../deprecated/robot-vision-tracking-algorithms.md) (deprecated): robot-vision tracking algorithms on `main`; Section 9 items "9.N".

## Tasks Done

1. [Reduced yaw update](#reduced-yaw-update) (F-2): detections without orientation give no yaw measurement.
2. [Per-model process noise](#per-model-process-noise) (F-1): each model's Q follows its own velocity; turn-rate noise for CTRV.
3. [Cholesky failure recovery](#cholesky-failure-recovery) (F-6, F-9, `a1883e810`): a covariance that cannot be factorised, or is non-finite, is repaired, not half-factorised.
4. [Sigma-point weights](#sigma-point-weights) (E-1): κ = 3 − n kept and documented.

## Tasks In progress

1. [Separate noise roles](#separate-noise-roles): meaning documented; r per deployment waits for the detection-noise measurement.

## Tasks Not started

1. [Measure the detection noise](#measure-the-detection-noise) per deployment after projection.
2. [Transition probability per unit time](#transition-probability-per-unit-time), derived from Δt.
3. [One prior mechanism](#one-prior-mechanism): floor rescale or Markov-predicted model probabilities.
4. [Covariance safety](#covariance-safety): process-noise floor on size (F-5, post-review plan PR 8).
5. [Robustness to jumps](#robustness-to-jumps): outlier-robust update (post-review plan PR 8 known issue).
6. [KPI tooling](#kpi-tooling): onset and release latency, evidence, per-model states.

## Details

### Context

#### Terms

| Term                                                      | Definition                                                                                                                                                                                                                                                                 | Code                                                                   |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Motion model                                              | State transition a filter predicts with. CV resets acceleration and turn rate, CA resets turn rate, CTRV resets acceleration                                                                                                                                               | [CV][cv], [CA][ca], [CTRV][ctrv]                                       |
| Nested models                                             | CA with zero acceleration and CTRV with zero turn rate predict exactly like CV                                                                                                                                                                                             | as above                                                               |
| Manoeuvre state                                           | The state only one model keeps: CTRV's turn rate w, CA's acceleration a                                                                                                                                                                                                    | as above                                                               |
| Model probability μ_j                                     | Belief that the target moves like model j; the μ_j sum to 1                                                                                                                                                                                                                | [`mModelProbability`][mu]                                              |
| Transition probability p_ij                               | Assumed probability that a target moving like model i moves like model j at the next predict. Fixed matrix, applied per predict (not per second), used only for mixing                                                                                                     | [matrix][transition]                                                   |
| Mixing, mixing weight μ(i\|j)                             | At each predict every model starts from a blend of all models' states and covariances, weighted μ(i\|j) ∝ p_ij·μ_i                                                                                                                                                         | [`combiningProbability`][combining], [`interaction`][interaction]      |
| Probability floor and ceiling                             | After the Bayes step every μ_j is rescaled linearly into [floor, ceiling]: no model leaves the range, and every update pulls all μ toward equal                                                                                                                            | [limits][limits], [rescale][rescale]                                   |
| Prior                                                     | Transition probability and floor together: assumptions applied every frame, whatever the detections say                                                                                                                                                                    | –                                                                      |
| Measurement noise R (r)                                   | Assumed detection noise; also the initial variance of the measured states                                                                                                                                                                                                  | [R][r], [config][config]                                               |
| Process noise Q_j                                         | Per-model noise added at each predict: velocity along and across the motion, acceleration (CA), turn rate (CTRV), yaw, and a small floor on the states the model resets. Scaled from the process-noise setting                                                             | [`processNoiseCov`][q], [per predict][qpredict]                        |
| Initial covariance P0                                     | Initial variance: the measured states start at r, the velocity at the initial-covariance setting; acceleration, yaw and yaw rate are capped at 0.1, 0.05 and 0.01                                                                                                          | [initial P][p0]                                                        |
| Predicted measurement ẑ_j, innovation ν_j, covariance S_j | Model j's prediction of the next detection, the detection minus the prediction, and its covariance (projected P plus R)                                                                                                                                                    | [UKF correct][ukfcorrect], [S][s]                                      |
| Likelihood Λ_j                                            | N(ν_j; 0, S_j): how well model j predicted the detection. The update multiplies μ_j by Λ_j, then normalises and rescales                                                                                                                                                   | [log-likelihood and update][loglik]                                    |
| Evidence                                                  | ln Λ_j − max over k≠j of ln Λ_k for one frame, in nats (1 nat multiplies the odds by e). Grows with (difference of the models' predictions)² / S. A diagnostic, not computed in the code                                                                                   | –                                                                      |
| Likelihood scale                                          | Absolute size of S. Scaling q, r and P0 together keeps each single filter's gains but scales the evidence                                                                                                                                                                  | –                                                                      |
| Reduced yaw update                                        | A detection without usable orientation (none, or dropped by the speed gate) leaves the yaw row out of the UKF update and the model likelihood (F-2). Before, it got the track's combined yaw as a pseudo-measurement                                                       | [rows][yawrows], [UKF][ukfreduced], [`prepareYawMeasurement`][yawprep] |
| Combined estimate                                         | μ-weighted mean and covariance of the models; what the tracker outputs                                                                                                                                                                                                     | [`combineStatesAndCovariances`][combine]                               |
| Association covariance                                    | S of the most probable model, used for gating                                                                                                                                                                                                                              | [best model][assoc]                                                    |
| Sigma-point parameters α, β, κ                            | UKF spread and weights of the sigma points                                                                                                                                                                                                                                 | [α, β][ukfparams], [κ][kappa]                                          |
| Published yaw                                             | Both services: once an orienting sensor was seen, the filter yaw, unless at 1 m/s or more it is over 0.6 rad off the velocity heading, then the heading. Otherwise the velocity heading with `rotation_from_velocity` (on above 1.0 m/s, off below 0.5 m/s), else identity | [Controller][pubctl], [Tracker][pubtrk]                                |

#### What is tuned

| Knob                                                                           | Where                                  | Acts on                                           |
| ------------------------------------------------------------------------------ | -------------------------------------- | ------------------------------------------------- |
| `default_measurement_noise` (r)                                                | [production constants][config]         | R, initial P of measured states, likelihood scale |
| `default_process_noise` (q)                                                    | production constants                   | Q of every model                                  |
| Q shape: velocity scale, cross-track ratio, turn-rate scale, yaw ratio, floors | [`processNoiseCov`][q]                 | Q per model                                       |
| `init_state_covariance` (P0)                                                   | production constants                   | initial latent variances                          |
| `motion_models`                                                                | production constants                   | which models compete                              |
| Transition probability, probability floor and ceiling                          | [matrix][transition], [limits][limits] | prior                                             |
| α, β, κ                                                                        | [constructor][ukfparams]               | sigma points                                      |

Neither service reads these from its config: the Controller and the Tracker set the robot_vision production constants (`kProduction*`, Python `PRODUCTION_*`).

#### How it is measured

Scenario tests drive one estimator with [`FilterRun`][filterrun] (no association), with truth from [`Trajectory`][trajectory] and a seeded [`Sensor`][sensor], in the production config.
Run several seeds and sensor noise levels. `ScenarioRecorder` (`RV_SCENARIO_DIR`) and `plot_scenario.py` / `render_video.py` (`tools/tracker/evaluation/visualization/README.md`) show the time series behind each number.

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

#### Trade-offs and relationships

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
- Yaw pseudo-measurement (before F-2) → penalised CTRV for turning its yaw, more as r shrank; the reduced yaw update removed it.
- Nested models → no evidence on steady straight motion; CV's μ there is not a KPI.
- Frame rate → the transition probability acts per predict, process noise per second: the effective prior changes with the frame rate.
- Association covariance → every noise change also changes gating (PR 4).
- Multiple cameras → Controller Immediate mode alternates camera biases, which look like noise; time-chunking averages them.
- κ → predicted mean under strong nonlinearity (CTRV with an uncertain w, long predicts) → coasting.

### Tasks Done

#### Reduced yaw update

- F-2 (`6277c8cf5`; yaw review 2): see [Terms](#terms). The pseudo-measurement penalised CTRV in turns, more as r shrank, held its turn rate back and cut the yaw variance every camera frame. Results in post-review plan PR 3.

#### Per-model process noise

- F-1 (#2056; yaw review E3, delta 9.8): each model's Q follows its own mixed velocity; CA gets acceleration noise, CTRV turn-rate noise 0.1 (rad/s)²/s, the states a model resets a 1e-6/s floor. Gives the IMM a signal: CTRV wins car turns (μ 0.18 → 0.57) and learns the turn rate (0 → 0.38 rad/s).

#### Cholesky failure recovery

- F-6 (`c4393854f`; baseline 9.4) and F-9 (`5fb7b1878`): a finite covariance that cannot be factorised is symmetrised and its eigenvalues raised to max(1e-9, 1e-12 λmax), with one warning; a repair that still fails falls back to a diagonal factor; double precision only. Never reached so far (2 h standing, 1 h circles, coasts, jumps). Since `a1883e810` a non-finite P gets a diagonal factor, with non-finite and tiny variances at 1e-9; a non-finite state is not repaired.

#### Sigma-point weights

- E-1 (`a222bd748`; baseline 9.4, delta 9.10): κ = 3 − n kept. The sigma points sit at √3 σ and the centre weight is −3, so the mean extrapolates from the centre point; with β = 2 the covariance stays positive semi-definite; only CTRV is nonlinear. No measurable effect at 10 fps (≤ 0.001 m) or 2 fps (≤ 0.01 m); one CTRV step with turn-rate variance 1 (rad/s)² gives 1.84 m/s against the exact 1.82 (κ = 0: 2.51). Documented in code and README; `CtrvPredictionKeepsGaussianMeanUnderTurnRateUncertainty` pins it.

### Tasks In progress

#### Separate noise roles

- r should be a measured sensor property per deployment; velocity, acceleration and turn-rate noise are target dynamics, not on r's scale. Their meaning is documented in the robot_vision README "Kalman filter settings" and the Python docstrings (`4ac31c2f7`; prob review 4). q, r and P0 are exposed in the service configs ([post-review plan PR 7](prob-tracking-post-review-plan.md#pr-7-per-detection-measurement-noise-r)). Remaining: r per deployment once [the detection noise is measured](#measure-the-detection-noise).

### Tasks Not started

#### Measure the detection noise

- Measure the detection noise per deployment after projection: random part and slowly varying bias, per camera. Unity's ground-truth boxes are not representative. The Tracker Evaluation camera projection run (`tools/tracker/evaluation/pipeline_configs/camera_projection_evaluation.yaml`) compares projected detections with ground truth. Needed for r, for the turn-offset decision (post-review plan PR 8) and for the R producer (post-review plan PR 7).

#### Transition probability per unit time

- The fixed transition matrix is applied per predict, process noise per second, so the effective prior changes with the frame rate. Derive the transition probability from Δt.

#### One prior mechanism

- Decide between the linear floor / ceiling rescale and Markov-predicted model probabilities (baseline 9.2): the μ update starts from the previous μ instead of the Markov prediction Σ_i p_ij μ_i, so the transition matrix acts only through mixing, and the rescale partly compensates. Neither alternative removed the turn offset (post-review plan PR 8).

#### Covariance safety

- Process-noise floor on size (F-5), tracked with its test in post-review plan PR 8 (z gets `vz` noise in PR 5): without it the size variance only shrinks and long-lived tracks stop following size changes. Needed so sharper settings cannot silently break covariances; the Cholesky repair acts only after the fact.

#### Robustness to jumps

- Disagreeing models mixed with a small S diverge: in `SingleJumpingDetectionTracking` (known-issue skip, post-review plan PR 8) a 200-sigma jump goes into CTRV's turn rate and splits the track. A smaller S makes this likelier; it needs an outlier-robust update.

#### KPI tooling

- In `test/support`: onset and release latency, evidence (not computed in the code), per-model states in the recorder (`estimator.jsonl` has only the combined state, P, μ, ẑ and S), and the scenario set of [How it is measured](#how-it-is-measured).

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
[p0]: https://github.com/open-edge-platform/scenescape/blob/8a315d93c895da676de2fd21c6b9997eb844b52b/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L106-L119
[ukfcorrect]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/UnscentedKalmanFilter.cpp#L189-L212
[s]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/UnscentedKalmanFilter.cpp#L224-L227
[loglik]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L519-L545
[yawprep]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/include/rv/tracking/OrientationAttributes.hpp#L111-L116
[combine]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L548-L571
[assoc]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L313-L328
[ukfparams]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/include/rv/tracking/MultiModelKalmanEstimator.hpp#L29
[kappa]: https://github.com/open-edge-platform/scenescape/blob/2804edf78edac60dead70d9c7077e0c13f385957/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L35
[pubctl]: https://github.com/open-edge-platform/scenescape/blob/8a315d93c895da676de2fd21c6b9997eb844b52b/controller/src/controller/ilabs_tracking.py#L191-L246
[pubtrk]: https://github.com/open-edge-platform/scenescape/blob/8a315d93c895da676de2fd21c6b9997eb844b52b/tracker/src/tracking_worker.cpp#L141-L162
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
[yawrows]: https://github.com/open-edge-platform/scenescape/blob/8a315d93c895da676de2fd21c6b9997eb844b52b/controller/src/robot_vision/src/rv/tracking/MultiModelKalmanEstimator.cpp#L29-L39
[ukfreduced]: https://github.com/open-edge-platform/scenescape/blob/8a315d93c895da676de2fd21c6b9997eb844b52b/controller/src/robot_vision/src/rv/tracking/UnscentedKalmanFilter.cpp#L248-L266
