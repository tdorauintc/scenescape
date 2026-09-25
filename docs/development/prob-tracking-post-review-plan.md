Sarat, my recommendation is to split the PR, so we can proceed granularly and carefully evaluate impact on accuracy and performance for each of them. Below is my proposal. I can take care of it.

What to extract into a new PRs to main branch:

1. Tracker shift projection + related evaluation update -> main
  - Tracker Evaluation pipeline change (to accept object class configuration)
  - Tracker Service - narrowed down to object-class and shift projection (w/o new association config)
2. Multicamera geometry fusion -> main
  - required supporting changes in Tracker / Controller
  - enabling robot-vision benchmark
  - related evaluation / fixes

What to extract into a new PR and merge first into a feature branch (keeping the order):

3. IMM-UKF changes -> feature branch
  - Carried over from feature/prob-tracking
    - Fixing IMM S_pred and mixing, process-noise redesign and the new initial uncertainty (MultiModelKalmanEstimator.cpp)
    - Fixing UKF (UnscentedKalmanFilter.cpp)
  - My proposed additions:
    - Introduce per-model process noise
    - Extend the tests coverage to include more motion models (manoeuvring motion, sudden stops)

4. Mahalonobis association -> feature branch
  - Carried over from feature/prob-tracking
    - New association implementation (ObjectMatching.cpp + any other changes required to support it)
    - Required supporting changes in Controller and Tracker Service to pass down association config and produce association window
    - Update Tracker Evaluation pipeline with new association configs
    - Manager UI support for association window
    - Related documentation
    - Extend the tests coverage
    - Robot-vision benchmark update
  - My proposed additions / fixes:
    - Extend the tests coverage
    - Evaluate using mixed convariance for matching instead of picking best model, then decide

5. Dataset and testing -> feature branch -> main
  - Final accuracy and performance evaluation

In parallel, I suggest Dmytro starts working on adopting a dataset with more diverse motion models in Tracker Evaluation (cars), to be merged into feature branch for final evaluation.

Let me know your feedback please.
