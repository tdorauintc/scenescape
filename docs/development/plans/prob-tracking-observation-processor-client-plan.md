<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# PR #2149 observation processor client: centre-of-mass tracker input (M1) and rename

## High level details

- Branch: `tdorau/prob-tracking-stp-client-side` (checkout `scenescape-prob-tracking-3d-R`) @ `c3ca618f1`: `fc3a0dc02` (pushed to `origin`) plus a temporary local commit that adds the observation processor proto (not pushed).
- PR: #2149 "ITEP-98103: [SPP] Tracker, Controller: experimental remote projection client" (draft). Base: `tdorau/prob-tracking-stp-tracker-refactor` (#2148 @ `b4c1e2e9d`), which is stacked on `feature/prob-tracking-extracted-3d-R`.
- Observation processor service (server): `origin/ITEP-98099_observation_processor_service` @ `d73820192`, not on `main` yet.
- Scope: fix review issue M1 (z reference vs measurement noise R), then rename "projection service" to "observation processor service" in all client-side names, and move the contract to `observation_processor/proto/observation_processor.proto`.
- Status: review, decisions, the earlier fixes, the plan approval, [A1](#a1-push-and-record-the-legacy-baseline) and A2–A9 and B1–B5 (pushed, PR head `8d97ccafd`; PR title and description updated) are done; Phase C (C1) is decided: no change in #2149, a robot_vision follow-up instead.
- Base update: #2148 moved from `b4c1e2e9d` to `7ab5d765c` (merged probabilistic tracking stack). The merge into the PR branch is committed locally as `db078b140` (parents `8d97ccafd` and `7ab5d765c`), pushed to `origin` (PR head); see [E1](#e1-merge-of-the-updated-base).
- Second base update: #2148 moved on to `c85677373` (Kalman filter settings, birth-clustering radius, non-planar Z with sticky `z_measured`, robot_vision field rename `zMeasured` → `z_measured`). The merge into the PR branch is staged locally, not committed; see [E2](#e2-merge-of-the-updated-base-again).

### Context

- The PR sends camera pixel boxes from the Tracker service and the Scene Controller to the observation processor service, and feeds each returned measurement and its R to robot_vision. It is behind an experimental option. See [What the PR does](#what-the-pr-does).
- M1: the contract returns the object's centre of mass with R for that point. The clients lower z by half the height but keep R, so R describes a different point than the one fed to the tracker (Copilot threads 2 and 5). See [M1](#m1-problem).
- Decision (option U): in experimental mode robot_vision receives centre-of-mass positions only, and published z is converted back to the footprint base. See [Decision](#decision-option-u).
- Experimental mode means the remote client is effectively in use (flag, host and port set, client created). Otherwise the service runs in legacy mode, which must stay bit-exact with the base branch. See [Gating](#gating-experimental-vs-legacy-mode).
- Assumption: in experimental mode every 3D input (`translation` from cameras and external sources) is the object's centre of mass. This must be documented. See [Consequences](#consequences).
- The contract is not changed semantically. The rename only switches to the server's file and names, and renames every Project/Projection name in the Tracker and Controller pipeline to Process/Processing. See [Rename](#rename-scope-and-names).
- Not changed: robot_vision, Manager/UI, Analytics and other services. The UI already draws a track at its published `translation` lifted by `size.z / 2`, i.e. it expects the base.
- Test-first: every implementation task is preceded by a task that lands failing tests. See [Verification](#verification-commands-and-environment).

### Related documents

Paths in backticks are relative to the PR branch checkout. Linked files are in this folder.

- [Post-review plan](prob-tracking-post-review-plan.md): the `feature/prob-tracking` split this PR builds on (PR 6 added 3D detection input and `zMeasured`).
- [IMM tuning guide](prob-tracking-imm-tuning.md): robot_vision noise and R background (default R = 0.2, hard-coded production noises).
- `observation_processor/proto/observation_processor.proto`: target contract. Committed temporarily on the PR branch (`c3ca618f1`, byte-identical to the server branch, not used by the build yet).
- [Context for starting A2](context/observation-processor-client-A2-start.md): the legacy baselines, the local-only harness and how to re-run the bit-exact check; for a new session.
- `api/projection/v1/projection.proto`: current contract copy. Same fields, old names; removed by [B1](#b1-switch-to-the-observation-processor-contract).
- `observation_processor/README.md` on the server branch: port 50052, plaintext gRPC, `OBSERVATION_PROCESSOR_*` env vars.
- `tracker/docs/implementation.md`, `docs/design/tracker-service.md`, `docs/user-guide/microservices/controller/how-to-configure-tracker.md`: client behaviour docs to update.
- `docs/user-guide/microservices/controller/data_formats.md`, `docs/user-guide/how-to-guides/publish-external-source-adapter.md`, `.github/skills/external-source-adapter/SKILL.md`: 3D `translation` docs that need the centre-of-mass assumption.
- `controller/src/robot_vision/README.md`: per-detection R (`measurementNoiseCov`) in robot_vision.

## Tasks Done

1. [PR review](#pr-review-and-copilot-comments): review of #2149, Copilot comments analysed, major issues M1–M4 identified.
2. [Client fixes](#client-fixes-commits): validation performance, M2, timeout bound, pins, optional diagnostics, dense-R tests, latency test, startup connect (`0d45ed48e` … `fc3a0dc02`).
3. [Copilot threads 1, 3, 4](#copilot-threads): fixed, reply texts prepared; the user posts them.
4. [M1 analysis](#m1-analysis-and-decision): options A, B, U, U′ and U2 compared with a robot_vision simulation; option U chosen with constraints.
5. [A1](#a1-push-and-record-the-legacy-baseline): `fc3a0dc02` pushed; reproducible legacy baselines of both services recorded on the PR base, with a local-only harness.
6. [A2](#a2-tracker-tests-red) + [A3](#a3-tracker-implementation-green): `21271d8f2` (Tracker, one commit). Tracker unit tests 623/623, `lint-cpp` clean, legacy differential bit-identical. Deviations: no `TrackingWorker::zReference()` getter (the scheduler tests assert the published z instead); a legacy pixel box publishes z = −2.8·10⁻¹⁸, not exactly 0, so the test allows 1e-9.
7. [A4](#a4-controller-tests-red) + [A5](#a5-controller-implementation-green): `e504e0699` (Controller, one commit). Python suites 562 passed, complexity and indent checks pass, legacy differential bit-identical. The output conversion is a helper, `_publishedPoint()`, because `from_tracked_object()` is at its complexity baseline (21). Legacy planar z is about 1e-17 in Python too, so the tests allow 1e-9 in both modes.
8. [A6](#a6-tracker-service-tests): `aa7e16b1c` (mock stops without the 10 s timeout) and `a843ec833` (z-reference checks folded into existing environments). Remote projection service tests 5/5 in 3:23 (was 4:38).
9. [A7](#a7-documentation): `5943773ef`. Tracker implementation notes, Tracker design, "Height Reference of Tracked Objects" in the tracker how-to, `translation` notes in the data formats, adapter how-to and skill.
10. [A8](#a8-verification-and-commit): verified on `5943773ef`: Tracker unit 623/623, `lint-cpp`, `lint-python`, Tracker service suite 16/16 (5:11, image built from `e504e0699`; later commits change no Tracker source), Python suites 562, complexity, indent, prettier (only an ignored local evaluation output is flagged), legacy differential bit-identical for both services. Commits were made per step instead of the three planned at the end.
11. [B1](#b1-switch-to-the-observation-processor-contract): `623dac291` (deletes `api/projection`) and `0c021a9de` (CMake, Dockerfiles, CI filter, codegen, imports, mock and compose switched to the server proto). The first commit alone does not build; the pair does. Both images built, stubs import with `python3 -W error`, Tracker unit 623/623, Python suites 562, remote service tests 5/5.
12. [B2](#b2-tracker-renames): `e40b88e5f`. Tracker pipeline types, files, config keys, env vars, metric and log messages renamed; geometric projection names kept. Tracker unit 623/623, `lint-cpp` and `lint-python` clean, remote service tests 5/5 (3:22). The mock folder, `mock_projection.py`, the compose service `mock-projection` and `test_remote_projection.py` keep their names for B4.
13. [B3](#b3-controller-renames): `d5ec6116d`. Module `observation_processor.py`, classes, env vars, CLI flag, metric and log messages renamed; the Controller tests use the new names. Python suites 562, complexity and indent pass, Controller image builds, imports with `-W error` and shows `--experimental-observation-processor`. The test folder `tests/sscape_tests/remote_projection/` and its test file keep their names for B4.
14. [B4](#b4-tests-mocks-compose-and-docs-renames): `8d97ccafd`. Test folders and files, the mock service (port 50052), compose service, profile and env vars, and the Tracker and Controller docs renamed. The residual check over the 62 files of this PR leaves only geometric names (`CoordinateTransformer` internals, `project_to_map`), pinhole-math prose, the per-category footprint settings comments, `compose_project_name` and the pose-adjustment help text.
15. [A9](#a9-copilot-threads-2-and-5): done; the user replied on threads 2 and 5.
16. [B5](#b5-verification-commit-and-pr-update): verified on `8d97ccafd`: Tracker unit 623/623, `lint-cpp`, `lint-python`, Python suites 562, complexity, indent, prettier on every changed doc and config file, both images built from HEAD (Controller stubs import with `-W error`), Tracker service suite 16/16 (4:51), legacy differential bit-identical for both services with the recorders compiled unchanged. Commits were made per step instead of one rename commit. PR title and description updated by the user.
17. [C1] 2D vs 3D birth clustering in robot_vision (Phase C). Decision: no change in #2149; the robot_vision fix is a follow-up in the [post-review plan](prob-tracking-post-review-plan.md#follow-up-work). A birth cluster keeps the `zMeasured` of its first detection, and its fused z averages every member, including pixel boxes without measured z. Probe (production settings; a pixel-box camera and two 3D sensors seeing two floors at the same XY; all 6 camera orders): 3 orders merge the floors at birth and 1 attaches the pixel box to the wrong floor, in legacy mode and for #2149 local-fallback inputs alike; the track splits after 1-2 frames. Remote measurements carry measured z, so they are unaffected (0 of 6).
18. [E1](#e1-merge-of-the-updated-base): merge of #2148 `7ab5d765c` into the PR branch. 12 conflicted files resolved, depth boxes (`distance`) kept local, legacy baselines re-recorded on the new base. Tracker unit 633/633, `tests/sscape_tests` 3748 passed, complexity, `lint-cpp`, prettier pass; legacy output of both services bit-identical to the new baselines. The merge commit is `db078b140`, pushed (PR head).
19. [E2](#e2-merge-of-the-updated-base-again): merge of #2148 `c85677373` into the PR branch (staged, not committed). 7 conflicted files resolved, `zMeasured` renamed to `z_measured` in the client code, legacy baselines re-recorded on the new base. Tracker unit 653/653, `tests/sscape_tests` 3892 passed, Tracker service suite 16/16, complexity, `lint-cpp`, `lint-python` and indent pass; legacy output of both services bit-identical to the new baselines.

## Tasks In progress

None.

## Tasks Not started

Phase D: follow-ups, out of scope.

1. [D1](#c1-follow-ups): server TLS (the server is plaintext), end-to-end accuracy evaluation with a real server, and planar z/vz noise if it matters to consumers, and one z reference in legacy mode.

## Details

### Context

#### What the PR does

- Behind an experimental option, the Tracker service (C++, per tracking scope) and the Scene Controller (Python, per scene) send the pixel boxes of each camera frame to the observation processor service over gRPC. One `ProcessDetections` call per camera frame runs concurrently under a deadline (`timeout_ms`, 1–100 ms).
- A valid measurement replaces the local projection of its detection: position, size (prior), `zMeasured = true` and per-detection R (`measurementNoiseCov`; Python `measurement_noise_covariance`). Yaw and `has_orientation` stay local.
- Failures keep the local projection, are counted (`tracker.remote_projection.failed_calls`, `scenescape_controller_remote_projection_failed_calls`; renamed in B) and are logged as rate-limited warnings.
- Contract measurement (both protos): `mean` has 7 values `[x, y, z, length, width, height, yaw]`. x, y, z is the object centre (centre of mass). Sizes are the size-prior means (`mu_z` for height). `noise_covariance` is a 7×7 row-major SPD matrix describing that mean. The server builds `mean = [*point, *priors[:3], 0.0]` (`observation_processor/src/observation_processor/conditioning.py` on the server branch).

#### M1 problem

- Both clients feed robot_vision `z = mean[2] - mean[5] / 2` (footprint base), but pass the contract R unchanged, and R describes the centre:
  - Tracker: `tracker/src/remote_projector.cpp`, `applyMeasurement()`.
  - Controller: `controller/src/controller/remote_projection.py`, `apply_measurement()`.
- Copilot (threads 2 and 5) proposed `J R Jᵀ` with `J[2,5] = -0.5`. Rejected: it folds the placeholder size variance (R_hh = 0.2) into z. That adds +0.05 m² to base z variance and gives a z–height correlation of about −0.75.
- Legacy inconsistency: pixel boxes enter robot_vision at the base (z = 0, `zMeasured = false`). 3D detections enter with their own z (`zMeasured = true`, usually the centre). A track fed by both settles between them: 0.425 m for h = 1.7 in simulation.
- robot_vision facts:
  - Every Kalman update, Euclidean distance and Mahalanobis gate (χ², 3 DoF) uses z. With no per-detection R, the default R_z = 0.2 m² applies.
  - `zMeasured` only selects XY vs XYZ birth clustering (`ObjectMatching.cpp`).
  - `isDynamic()` uses the 3D speed (> 1 m/s).

#### Decision: option U

Experimental mode:

- Input, after local projection and remote measurement application:
  - Each robot_vision input with `zMeasured == false` (camera pixel boxes, AprilTags, pixel boxes from external sources) gets `z += height / 2`.
  - Remote measurements are fed as received: `z = mean[2]`, R unchanged.
  - Other `zMeasured` inputs (camera `translation`, external source `translation`) are unchanged; they are assumed to be centre of mass.
- Output: every published track gets `z = rv_track.z - rv_track.height / 2`. x, y, velocity (vz included), size and yaw are unchanged.
- robot_vision itself is unchanged.

Legacy mode: no conversion at all. The code path must stay identical to the base branch, so outputs are bit-exact.

#### Gating: experimental vs legacy mode

The mode follows the switches that already choose remote vs local projection ("effective" gating). It is fixed for the process lifetime; changing it requires a restart, so tracks never mix references.

- Tracker:
  - `makeProjectorFactory(config, connect)` (`tracker/src/remote_projector.cpp`) returns a non-empty factory only when all of these hold: the experimental flag is true, `infrastructure.remote_projection` has host and port, and the client was created.
  - `TimeChunkScheduler::get_or_create_worker()` (`tracker/src/time_chunk_scheduler.cpp`) uses the injected-projector `TrackingWorker` constructor only in that case. That is where the worker gets the centre-of-mass mode. The legacy constructor means legacy mode.
- Controller:
  - `remote_projection.for_scene(uid, chunking_rate_fps)` returns a `SceneProjection` only when the env flag, host and port are set and the client was created.
  - `Scene._bindRemoteProjection()` (`controller/src/controller/scene.py`) binds it to `tracker.remote_projection`. Category trackers inherit it (`tracking.py`, `time_chunking.py`).
  - Experimental mode applies when `self.remote_projection is not None`. A4 checks that the binding happens before the first detection reaches the tracker.

#### Consequences

Measured with production robot_vision settings (IMM, noises, 0.99 Mahalanobis gate), 15 fps, planar XY noise σ = 0.1 m, 20 seeds. A4 encodes them as tests.

| Track type in experimental mode                              | Effect                                                                                                                                                                                                                                                                       |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Remote measurements only                                     | Output identical to the current PR, up to floating-point rounding (constant offset).                                                                                                                                                                                         |
| Planar only, constant height                                 | Exact: published z equals the legacy z.                                                                                                                                                                                                                                      |
| Planar only, per-frame box height (default in both services) | Published z noise RMS 5.1 cm (σ_h = 0.08 m) / 6.3 cm (σ_h = 0.25 m), max 11 / 21 cm. vz RMS 3.5 / 5.2 cm/s, max 0.09 / 0.20 m/s. Legacy publishes exactly 0. XY identical (≤ 2·10⁻¹³ m); no extra fragmentation; static/dynamic classification unchanged.                    |
| 3D camera `translation`, external sources                    | Published z = input z − h/2 (centre → base). A source that actually sends its base is published h/2 too low; e.g. `tests/functional/test_z_tracking.py` inputs would be published at −0.9 m. The functional stack runs in legacy mode, so that test keeps passing unchanged. |
| Mixed planar + 3D (+ remote)                                 | Consistent reference (no midpoint bias), so fusion, gating and XYZ birth clustering agree.                                                                                                                                                                                   |
| Legacy mode                                                  | Bit-exact with the base branch (A1/A8 differential).                                                                                                                                                                                                                         |

Other cases:

- Controller planar points with non-zero z (AprilTag hover distance; 3D plane origins in `MovingObject`) round-trip unchanged, up to the filter noise above.
- A height of 0 gives no shift.
- The published association window and covariance are XY only, so they are unaffected.

#### Rename scope and names

- The concept "projection service" / "remote projection" becomes "observation processor service" / "observation processor" everywhere: comments, types, functions, variables, files, config keys, env vars, CLI flags, metrics, logs, docs and this plan.
- The local pipeline terms from #2148 are renamed too, in both the Tracker and the Controller. Every name with Project / Projector / Projection / Projected in it becomes Process / Processor / Processing / Processed, with an "Observation" qualifier where the name would otherwise be generic. Examples:
  - `ProjectedDetections` → `ProcessedObservations`
  - `DetectionProjector` → `ObservationProcessor`
  - `CameraModelProjector` → `CameraModelProcessor`
  - `ProjectorFactory` → `ObservationProcessorFactory`
  - `RemoteProjector` → `RemoteObservationProcessor`
  - the term "local projection" → "local processing"
  - The full maps are in [B2](#b2-tracker-renames) and [B3](#b3-controller-renames).
- Names that refer to the remote service keep "observation processor": `ObservationProcessorClient`, `GrpcObservationProcessorClient`, `ObservationProcessorFrame`, `ObservationProcessorReply`, env vars, config keys, CLI flag, metrics. The endpoint config becomes `RemoteObservationProcessorConfig`, matching `RemoteObservationProcessor`, because `ObservationProcessor` is now the interface name.
- Not renamed, because these names describe geometric projection math, not the pipeline role:
  - `CoordinateTransformer` internals such as `bbox_projection_indices`;
  - `MovingObject._projectBounds` / `projectToMap` and its `project_to_map` attribute;
  - scene_common `getMeshAxisAlignedProjectionToXY`;
  - robot_vision;
  - the contract field `project_to_map`;
  - prose describing the pinhole math ("projects the box bottom-centre onto the ground plane").
  - Documents outside #2148/#2149 that use "projection" for other concepts: ADR-0013's "Spatial Transform & Projection Service" (a broader architectural service on `main`) and camera-geometry docs such as the PTZ pose design ("reprojection").
  - Override at plan review if these should change too.
- Phase A uses the current names. Phase B renames them, including the code Phase A adds, e.g. the `TrackingWorker` processor constructor parameter.
- Contract: use `observation_processor/proto/observation_processor.proto` from the server branch, at that location:
  - package `scenescape.observation_processor.v1`, service `ObservationProcessorService`, rpc `ProcessDetections`, messages `ProcessDetectionsRequest` / `ProcessDetectionsResponse`;
  - all other messages and fields are identical, including `include_diagnostics = 6`.
- The server listens in plaintext (`add_insecure_port`) on port 50052 by default. The clients default to TLS, so deployments need `*_INSECURE=true` until [C1](#c1-follow-ups).

#### Verification commands and environment

- Tracker unit tests: `make -C tracker test-unit` (conan debug build, about 1 min).
- Format: `make -C tracker lint-cpp` (clang-format 18). Tracker Python lint: `make -C tracker lint-python` needs `autopep8` on PATH.
- Tracker service tests:
  - Build a custom-tagged image; `make build-image` also retags `:latest`. Command: `docker build --target runtime --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) --build-arg BUILD_TYPE=Release -t intel/scenescape-tracker:<tag> -f tracker/Dockerfile .`
  - Run: `cd tracker/test/service && VERSION=<tag> .venv/bin/pytest -v` (16 tests, about 5 min). Unset `TRACKER_MQTT_*`.
- Python tests:
  - Generate secrets once with `make init-secrets`.
  - Run with proxy variables unset: `env -u http_proxy -u https_proxy tests/.venv/bin/python -m pytest tests/sscape_tests/remote_projection tests/sscape_tests/scene_pytest tests/sscape_tests/scenescape tests/sscape_tests/robot_vision -q -p no:cacheprovider` (554 passed at `fc3a0dc02`).
- Complexity: `make complexity-check SERVICE=controller` with `complexipy == 8.1.0` (pinned in `.github/resources/requirements.txt`) on PATH. Also `make indent-check`.
- Docs: `make prettier-check` (CI); fix with `make prettier-write`.
- Controller image (needed for B1): `make -C controller IMAGE=intel/scenescape-controller-<tag> VERSION=check` keeps your other images untouched.

### Tasks Done

#### PR review and Copilot comments

- Review of #2149 found M1 (R/z reference mismatch), M2 (malformed statuses fell back silently), M3 (unbounded timeout on the worker path) and M4 (slow controller validation).
- Copilot raised 5 comments, all valid; M1 corresponds to threads 2 and 5.

#### Client fixes (commits)

- `0d45ed48e`: the controller validates R once, in the robot_vision setter; about 2.5× less client CPU. The tracker keeps its hand-written 7×7 Cholesky: OpenCV 4.13 from conan was slower and changed accept/reject results.
- `91a2574ed`: only `DEPTH_UNOBSERVABLE` falls back silently; `OK` without a measurement, `UNSPECIFIED` and unknown statuses count as `invalid_measurement`.
- `313ca8e98`: `timeout_ms` is bounded to 1–100 ms (schema and env) and a warning is logged above the chunk interval. No custom backoff: gRPC fails fast and backs off reconnects.
- `d8d5fd2c3`: controller runtime pinned to `grpcio==1.85.0` and `protobuf==7.36.2`; stubs generated by `grpcio-tools==1.71.2`.
- `862799db5`: the `include_diagnostics` request field gates `frustum`/`amodal`; about 33% smaller responses.
- `619bec940`: unit tests in both clients use a dense SPD R and assert all 49 entries exactly.
- `cd8fd19e8`: the latency service test also runs 2 cameras × 50 detections. With a 0 ms mock, remote adds +3.8 ms to the transform stage and +4 ms to the median end-to-end latency.
- `40a0482fb` (user): docs explain why local projection runs on every frame.
- `fc3a0dc02` (local only): both clients connect at startup, fixing the first-call `DEADLINE_EXCEEDED`. Regression check: tracker 613/613, Python 554, tracker service suite 16/16.

#### Copilot threads

- Thread 1, `controller/src/controller/remote_projection.py`: "Fixed in 91a2574ed: OK without a measurement (and UNSPECIFIED or unknown statuses) now counts as invalid_measurement; only DEPTH_UNOBSERVABLE falls back silently."
- Thread 3, `tracker/schema/config.schema.json`: "Fixed in 313ca8e98: timeout_ms is now limited to 1–100 ms in the schema and env parsing, so 2147483648 fails validation (covered by a config loader test)."
- Thread 4, `tracker/src/grpc_projection_client.cpp`: "Fixed in 91a2574ed: only DEPTH_UNOBSERVABLE skips validation; OK without a measurement, UNSPECIFIED and unknown statuses carry no values and count as invalid_measurement."
- Threads 2 and 5: handled by [A9](#a9-copilot-threads-2-and-5).

#### M1 analysis and decision

| Option | Summary                                | Outcome                                           |
| ------ | -------------------------------------- | ------------------------------------------------- |
| A      | `J R Jᵀ` in the clients                | Rejected (placeholder variance).                  |
| B      | Keep base, R unchanged                 | Base error misses σ_h²/4 ≈ 0.0056 m² for persons. |
| U      | Centre of mass in, base out            | Chosen.                                           |
| U′     | Per-source conventions                 | Not chosen.                                       |
| U2     | Base everywhere, 3D converted at input | Exact planar, approximate R.                      |

Constraints added by the user:

- The conversion is applied only in experimental mode (effective gating), and legacy mode is bit-exact.
- External sources are assumed to send centre of mass; document it.
- Keep the functional z-tracking test unchanged and cover centre of mass in controller unit and tracker service tests.
- Rename to "observation processor" and use the server proto at its location.

#### A1. Push and record the legacy baseline

- Pushed `fc3a0dc02`; `origin/tdorau/prob-tracking-stp-client-side` is at the PR head.
- The baselines below were recorded on `b4c1e2e9d` and are superseded by the ones recorded on `7ab5d765c`; see [E1](#e1-merge-of-the-updated-base). The workflow is unchanged.
- Baselines recorded on the PR base `b4c1e2e9d` in the local worktree `/tmp/m1-base`, by two recorders that are local only and never committed (see [the context document](context/observation-processor-client-A2-start.md)):
  - Controller: real `IntelLabsTracking` with production robot_vision settings, through `trackCategory()` and `trackCategoryBatched()`; 1,500 frames, 7,691 robot_vision inputs (1,230 `zMeasured`), 10,498 published objects (7,509 with z exactly 0, the planar tracks). Inputs: planar pixel boxes with per-frame heights, AprilTag objects with hover z, 3D `translation` objects; observation processor unset.
  - Tracker: legacy `TrackingWorker` constructor with a fixed clock; 300 chunks × 2 scopes. Scope A is mixed (cam-1 planar boxes plus 3D detections from both cameras), scope B is planar only; every 50th chunk is empty. Track IDs are normalised by first appearance, and every value is recorded as hexfloat.
  - Each baseline was reproduced by three identical runs.
- Sanity check: both recorders on the PR head `fc3a0dc02` give output bit-identical to the base, so legacy mode is already bit-exact today and any later difference comes from the M1 work.
- Re-check: `check_legacy.sh [tree]` in the local harness folder reruns both recorders and diffs them against the baselines (about 1 minute with an up-to-date Tracker build).
- Note 1: pixel boxes must end below the horizon. The camera model intersects the box foot with the ground, so a box whose bottom is above the principal point (`y + height < cy`, 360 px for the 1280×720 test cameras) projects thousands of metres away. Objects built from such boxes then "move" at tens of m/s and never become reliable tracks. This made the first recordings useless, and it applies to every new test that feeds pixel boxes and needs realistic positions or motion. Use boxes such as `{x, 400, 55, 150}` (foot 190 px below the horizon, about 14 m from a camera 3 m high looking straight down). Stationary boxes are unaffected, so the existing service-test boxes `BBOX` and `GRID_BOXES` work but their local projections are far away.
- Note 2: the Tracker recording takes planar boxes from `cam-1` only. Planar boxes of two differently posed cameras overlap in world coordinates, the associations flip between frames and no track becomes reliable. Multi-camera fusion in the Tracker recording is covered by 3D detections from both cameras. The multi-camera planar path is covered by the Controller recording only.

#### E1. Merge of the updated base

- Base: #2148 moved from `b4c1e2e9d` to `7ab5d765c`. Merge commit `db078b140` in the `scenescape-prob-tracking-client` checkout; it includes the depth-box change and the test fix below. It brings the probabilistic tracking stack: Mahalanobis association (ADR-0019), PTZ pose consumption, moving external objects and `track=false`, nested camera observations of external sources, depth boxes (`distance`), the tracker `_lifecycle_lock` and the `tracking_radius` gate with a birth cluster radius. `robot_vision` is not changed by the PR, so the merged tree uses the base's.
- 12 files conflicted. Resolutions:
  - `ilabs_tracking.py`: keep `_toTrackerReference()` and `_publishedPoint()`; take the base's `_association_kwargs()`, `_birth_cluster_radius()` and `_warn_ignored_tracking_radius()`. `update_tracks()` and `update_tracks_batched()` call `_toTrackerReference()` first, then `track(**self._association_kwargs(...))`. The old `_warn_deprecated_tracking_radius()` and the `association_match_params()` calls in the two update methods are gone.
  - `tracking.py` and `time_chunking.py`: take the base's `_lifecycle_lock` / `_joined` structure and keep `tracker.observation_processor = getattr(self, 'observation_processor', None)` inside the lock, so a category tracker created while the scene is bound still inherits the processor.
  - `metrics.py`, `controller-cmd`, `Agents.md`, `controller.md`: keep both sides (observation processor and PTZ).
  - `tracker/config/tracker.json`: the base's `"association": {"method": "euclidean"}` (the base reverted the shipped configs to Euclidean) plus `experimental_observation_processor` and `observation_processor_mode`. `config_loader.hpp`: the base's ADR-0019 comment plus the two fields.
  - `data_formats.md`, the adapter how-to and the adapter skill: the base's text (nested camera observations in camera-local metres, `track=false` rules) plus the centre-of-mass note. `data_formats.md` also says that `track=false` objects bypass the tracker and keep the reported `z`, so they are not converted.
- Indirect changes:
  - Depth boxes: a pixel box with `distance` has `zMeasured == false` and a bottom-centre location, so option U handles it (input `+h/2`, output `-h/2`). But the service would replace the sensor depth and size with the monocular estimate, and a failed call would keep the depth placement, so the result would depend on the service. `_pixel_box()` now skips objects with `metric_distance`, like measured-z objects, and `test_sends_only_pixel_boxes_of_scene_cameras` covers it. The Tracker service has no `distance` support, so nothing changes there.
  - The test `test_category_trackers_inherit_scene_processor` builds the tracker with `__new__`; it now sets `_joined` and `_lifecycle_lock`, which `_createTrackers()` needs.
  - Moving external objects (`track=false`) never reach robot_vision, so they get no z conversion in either mode.
- Legacy baselines re-recorded on `7ab5d765c` (local worktree `/tmp/m1-base2`, removed afterwards; same recorders, each run twice and reproducible). The association change alters the legacy output, so the old baselines no longer apply:
  - Controller: 1,500 frames, 7,691 robot_vision inputs (1,230 `zMeasured`), 10,248 published objects (was 10,498), 19,439 lines.
  - Tracker: 300 chunks × 2 scopes, 3,101 lines.
  - The old recordings are kept in the harness folder under `b4c1e2e9d/`. `check_legacy.sh` now defaults to the `scenescape-prob-tracking-client` checkout and its `tests/.venv` (the venv of the old `3d-R` checkout has an outdated `robot_vision`).
- Verification on the resolved tree:
  - Tracker unit 633/633 (the base added tests), `lint-cpp` and `lint-python` clean.
  - `tests/sscape_tests`: 3748 passed, 15 skipped; the four PR suites alone: 984 passed.
  - `make complexity-check SERVICE=controller` passes (490 functions, 25 allowances), `make prettier-check` passes, `checkIndent` passes on every changed Python file. `make indent-check` over the whole tree fails before the merge commit (it lists files that the merge deletes or renames) and passes on `db078b140`.
  - `check_legacy.sh`: Controller and Tracker output bit-identical to the new baselines.
  - Not run: Tracker service suite (needs images built from the merged tree).

#### E2. Merge of the updated base again

- Base: #2148 moved from `7ab5d765c` to `c85677373`. New: Kalman filter settings and the birth-clustering radius in both services (`filter` block, `birth_cluster_radius_m`), non-planar Z / vz with sticky `z_measured`, `position_gate` helpers, the black-box configs back to `euclidean`, and the robot_vision field rename `zMeasured` → `z_measured` (C++ and Python).
- 7 files conflicted, all resolved by keeping both sides: `scene.py` (imports), `config_loader.hpp` (fields and constants), `config_loader.cpp` (the observation processor env, then the base's birth-radius and filter env), `observation_processor.hpp` and `tracker/docs/implementation.md` (our names, `z_measured`), `how-to-configure-tracker.md` (Kalman Filter Settings, then Experimental Observation Processor; prettier-formatted), `tracking_worker_test.cpp` (the base's `BuildTrackerConfigTest` block plus our `CallbackProcessor`).
- Indirect changes:
  - `zMeasured` → `z_measured` everywhere the client touches robot_vision: `ilabs_tracking.py` (`_toTrackerReference`), `observation_processor.py`, `z_reference.hpp`, `remote_observation_processor.cpp`, their tests and the docs. These merged without a conflict and failed at runtime or compile time. The comment in `observation_processor.proto` stays: the file is byte-identical to the server's.
  - Option U still holds with sticky `z_measured`: a track that has measured z (remote measurement or 3D detection) ignores z of later planar updates, so a fallback pixel box (raised by `h/2`) no longer pulls it. New test `test_planar_fallback_does_not_pull_a_measured_z_track`; one sentence added to the how-to and the Tracker implementation notes.
  - The doc numbers for planar-only tracks (z noise, vz noise) are unchanged: the same simulation on the old and the new robot_vision gives identical values (planar-only tracks never set `z_measured`).
  - The old robot_vision in `tests/.venv` had no `position_chi2`; it was rebuilt from the merged tree.
- Legacy baselines re-recorded on `c85677373` (local worktree `/tmp/m1-base3`, removed afterwards; each run twice, reproducible): Controller 1,500 frames, 7,691 inputs, 10,171 published objects (was 10,248), 19,362 lines; Tracker 3,101 lines. `py_record.py` reads `z_measured`. The previous recordings are kept in the harness folder under `7ab5d765c/`.
- Verification on the merged working tree (staged, not committed): Tracker unit 653/653 (1 skipped golden writer), `lint-cpp`, `lint-python`; `tests/sscape_tests` 3892 passed, 15 skipped; `make complexity-check SERVICE=controller` (494 functions), `make indent-check`; Tracker service suite 16/16 (image built from the merged tree, 3:36); `check_legacy.sh`: Controller and Tracker output bit-identical. `make prettier-check` fails only on `docs/design/probabilistic-tracking-association.md`, which the base already ships unformatted.

### Tasks In progress

None.

### Tasks Not started

#### A2. Tracker tests (red)

- Pixel boxes in the new tests end below the horizon ([A1 note 1](#a1-push-and-record-the-legacy-baseline)). With the worker-test camera (3 m high, straight down, `cy = 360`) use e.g. `{600, 420, 55, 150}`. The box `{10, 20, 50, 100}` of the older worker tests projects thousands of metres away and is unsuitable here.
- New `tracker/test/unit/z_reference_test.cpp` (register in `tracker/test/unit/CMakeLists.txt`) for new helpers in `tracker/inc/z_reference.hpp`:
  - `ZReference { FootprintBase, CentreOfMass }`.
  - `toCentreOfMass(std::span<std::vector<rv::tracking::TrackedObject>>)`: objects with `zMeasured == false` get `z += height / 2`; `zMeasured` objects are untouched; height 0 gives no change.
  - `footprintBaseZ(const rv::tracking::TrackedObject&)`: returns `z - height / 2`.
- `tracker/test/unit/tracking_worker_test.cpp`:
  - `Legacy_PublishesTrackerZUnchanged`: legacy constructor; a pixel box publishes `translation[2] == 0.0` (exact), and a `translation` detection with world z 0.9 publishes 0.9 (±1e-9).
  - `CentreOfMass_PixelBoxPublishedAtBase`: injected constructor with `CameraModelProjector` and `ZReference::CentreOfMass`; identical boxes publish |z| < 1e-9.
  - `CentreOfMass_TranslationTreatedAsCentre`: world z 0.9 with size height 1.8 publishes 0.0 (±1e-9).
  - `CentreOfMass_RemoteMeasurementAtCentre`: a fake projector returns `zMeasured` z = 0.85 with height 1.7 and publishes 0.0 (±1e-9). Velocity, size and XY are equal to the legacy run.
  - Add a `TrackingWorker::zReference()` getter for scheduler tests.
- `tracker/test/unit/time_chunk_scheduler_test.cpp`:
  - `Dispatch_UsesProjectorFactoryForNewWorkers` additionally asserts `CentreOfMass`.
  - New `Dispatch_WithoutFactoryUsesFootprintBase`.
- `tracker/test/unit/remote_projector_test.cpp`: in `expectRemote()`, z equals `kHeight / 2.0` (centre, not lowered); update its message. All other assertions are unchanged (dense R, all 49 entries).
- Expected red: the new symbols don't compile yet, and the `expectRemote` z assertion fails.

#### A3. Tracker implementation (green)

- `tracker/inc/z_reference.hpp` (+ `src/z_reference.cpp` if not header-only): the helpers from A2. Add the source to `PROJECT_SOURCE_LIST` in `tracker/CMakeLists.txt` if needed.
- `tracker/inc/tracking_worker.hpp` and `tracker/src/tracking_worker.cpp`:
  - The injected-projector constructor gets a `ZReference z_reference` parameter. The legacy constructor stays `FootprintBase` with no new code on its path.
  - After `transform_detections()` builds `objects_per_camera` (around `tracking_worker.cpp:315–343`) and before `tracker_.track(...)` (around line 426): `if (z_reference_ == ZReference::CentreOfMass) toCentreOfMass(objects_per_camera);`
  - Where tracks are built (around line 377, `track.translation = {rv_track.x, rv_track.y, rv_track.z}`): z is `footprintBaseZ(rv_track)` in `CentreOfMass` mode and `rv_track.z` otherwise. Check that no other code reads `rv_track.z`.
- `tracker/src/time_chunk_scheduler.cpp`: in `get_or_create_worker()`, the factory branch passes `ZReference::CentreOfMass`.
- `tracker/src/remote_projector.cpp`: `applyMeasurement()` sets `object.z = mean(2)`. Update the class doc in `tracker/inc/remote_projector.hpp` ("centre z is lowered…" → "centre of mass, converted to the footprint base on output by the worker").
- Acceptance: `make -C tracker test-unit` is all green; `make -C tracker lint-cpp` is clean.

#### A4. Controller tests (red)

All in `tests/sscape_tests/remote_projection/test_remote_projection.py`:

- `TestApplyMeasurement.test_sets_base_position_size_and_noise`: rename to `..._centre_position...`; z == `HEIGHT / 2` (centre). `assert_remote()` asserts z == `HEIGHT / 2`.
- `TestTrackerIntegration`, rv inputs captured by the `Mock` tracker:
  - Experimental (projection bound): remote object z == `HEIGHT / 2`; planar object z == `0.0 + 1.5 / 2` (`detected_object` size height 1.5); a `has_measured_z` object keeps its z.
  - Legacy (`remote_projection = None`): z of all inputs equals the input exactly.
  - Cover both `update_tracks()` and `update_tracks_batched()`.
- Output conversion, `from_tracked_object()`:
  - Experimental: published `location[0].point.z == tracked.z - tracked.height / 2`.
  - Legacy: published z equals `tracked.z` exactly.
- New `TestZReferenceWithRobotVision`, real robot_vision with production config (see `IntelLabsTracking.__init__`) and `association_match_params()`, 15 fps, 30 s:
  - Experimental, planar-only, constant height 1.7: published |z| < 1e-9 and |vz| < 1e-9.
  - Experimental, `translation` z = 0.9, height 1.8: published z = 0.0 (±1e-9).
  - Legacy, same inputs: planar 0.0 exactly; translation 0.9 (±1e-9).
  - Characterization, experimental planar, per-frame height `1.7 + 0.12·sin(2πt/8) + N(0, 0.08)` with a fixed seed: |z| < 0.25 m, |vz| < 0.3 m/s; XY within 1e-9 of the legacy run with the same seed; one track per object.
- Binding order: a test that `Scene.deserialize()` binds `remote_projection` before the tracker receives objects, and that `_setTracker()` rebinds. Add a guard only if the test shows mixing is possible.
- Expected red: z assertions in the apply and integration tests, and the output conversion tests.

#### A5. Controller implementation (green)

- `controller/src/controller/remote_projection.py`: `apply_measurement()` sets `rv_object.z = mean[2]`. Update the module docstring: centre of mass internally, base on output.
- `controller/src/controller/ilabs_tracking.py`:
  - `_applyRemoteProjection(objects_per_camera, rv_objects_per_camera)`:
    - Rename it to state its role, e.g. `_toTrackerReference`.
    - After the observation processor measurements are applied, each rv input with `zMeasured == False` gets `z += height / 2`.
    - Only when `self.remote_projection is not None`.
  - `from_tracked_object()`: when `self.remote_projection is not None`, use `Point(x, y, z - height / 2)`. The early-return path for `all_tracker_objects` is unchanged.
  - Legacy path: no new arithmetic.
- Acceptance: the Python suites from [Verification](#verification-commands-and-environment) are green. `make complexity-check SERVICE=controller` and `make indent-check` pass.

#### A6. Tracker service tests

- Runtime budget (user decision): the PR's service tests, `tracker/test/service/test_remote_projection.py`, stay below 5 minutes. Each compose environment costs about 20–30 s, so A6 starts no new environment:
  - `test_remote_projection_measurements_drive_tracks` (experimental) also sends the same 3D `translation` in two categories, with heights 1.8 m and 0.2 m. The published z differ by −0.8 m (z = centre − h/2) and XY are equal (±0.01). This replaces the planned `test_translation_detection_z_reference` (one legacy and one experimental environment); legacy `translation` z is covered by the Tracker unit tests and the A8 differential.
  - `test_remote_projection_failure_keeps_local_projection` (unavailable and deadline) asserts |z| < 0.01 on the local track: local inputs are converted even when every call fails. This replaces the planned `test_local_fallback_publishes_base_z`.
  - `mock-projection` gets `init: true` in `tracker/test/service/compose.yml`. The mock server ran as PID 1 and ignored SIGTERM, so each `compose down` waited for the 10 s stop timeout; 7 of the 9 environments start the mock.
  - Measured (5 tests, this machine): 4:38 with the folded checks before the `init` fix, 3:23 after. The two latency tests take 145 s (3 environments each). The plan as written would have added 3 environments, about 1–1.5 minutes.
- Pixel boxes: new tests that need realistic local positions or moving boxes use boxes that end below the horizon ([A1 note 1](#a1-push-and-record-the-legacy-baseline)), e.g. `{x, 400, 55, 150}` for the 1280×720 `atag-qcam*` cameras. The existing stationary `BBOX` and `GRID_BOXES` stay as they are; their local projections are far from the scene, which does not affect these tests.
- Docstrings of the module and of the two tests: centre of mass fed to the tracker, footprint base published.
- Acceptance: `test_remote_projection.py` green against a custom-tagged image; the full service suite runs in A8.

#### A7. Documentation

- `tracker/docs/implementation.md`:
  - Replace "lowers the returned centre z by half the height to the object base" with a subsection "z reference in experimental mode": centre-of-mass input rule, base output rule, legacy unchanged, gating.
  - Update the 3D paragraph ("3D detectors usually report the box centre…"): mixed references are resolved in experimental mode.
- `docs/design/tracker-service.md` (experimental observation processor section) and `docs/user-guide/microservices/controller/how-to-configure-tracker.md` (the paragraph "The returned position is the object centre…"):
  - The same rules.
  - The 3D centre-of-mass assumption.
  - The planar z/vz noise numbers from [Consequences](#consequences).
- `docs/user-guide/microservices/controller/data_formats.md`: in the `translation` rows (camera detections, external-source objects), add a note that with the experimental option enabled, `translation` is interpreted as the object's centre of mass and published tracks report the footprint base.
- `docs/user-guide/how-to-guides/publish-external-source-adapter.md` and `.github/skills/external-source-adapter/SKILL.md`: adapters must send the centre of mass in `translation`.
- Docstrings and comments: `tracker/inc/remote_projector.hpp`, `controller/src/controller/remote_projection.py`, `controller/Agents.md` if it describes the lowering, and the docstring of `tracker/test/service/test_remote_projection.py`.
- Acceptance: `make prettier-check` passes.

#### A8. Verification and commit

- Run the full matrix from [Verification](#verification-commands-and-environment): tracker unit, `lint-cpp`, `lint-python`, the tracker service suite (custom image), the Python suites, complexity, indent and prettier.
- Legacy bit-exact differential: run the local `check_legacy.sh` on HEAD (see [A1](#a1-push-and-record-the-legacy-baseline)); both recordings must be identical to the base ones. The script installs the Tracker recorder temporarily and removes it on exit; before committing, check that `git status` shows neither the harness nor its CMake registration. Multi-camera planar fusion is covered only by the Controller recording ([A1 note 2](#a1-push-and-record-the-legacy-baseline)).
- Commits (each with the `Co-authored-by` trailer), in test-first order:
  - "Tracker: feed centre-of-mass positions to robot_vision with the observation processor"
  - "Controller: feed centre-of-mass positions to robot_vision with the observation processor"
  - "Docs: z reference with the experimental observation processor"
- Commit messages carry the before/after evidence: differential empty, planar noise numbers.

#### A9. Copilot threads 2 and 5

- After the push, the user posts on both threads: "Fixed in 21271d8f2 (Tracker) and e504e0699 (Controller): in experimental mode the clients feed robot_vision the contract's centre-of-mass mean with its R unchanged, and convert z to the footprint base only on output, so R needs no transform."

#### B1. Switch to the observation processor contract

- The proto is already on the PR branch as the temporary commit `c3ca618f1` (no `git add` needed). Verify it is still byte-identical to `origin/ITEP-98099_observation_processor_service:observation_processor/proto/observation_processor.proto`, so the later merge is a clean add/add. Delete `api/projection/` (and `api/` if empty).
- Tracker CMake (`tracker/CMakeLists.txt`):
  - Import dir `${CMAKE_CURRENT_LIST_DIR}/../observation_processor/proto`.
  - Target `tracker_projection_proto` → `tracker_observation_processor_proto`.
  - Includes `"projection/v1/projection.grpc.pb.h"` → `"observation_processor.grpc.pb.h"`; namespace `scenescape::observation_processor::v1`; stub `ObservationProcessorService`, method `AsyncProcessDetections`, messages `ProcessDetectionsRequest/Response`.
- `tracker/Dockerfile`: `COPY observation_processor/proto observation_processor/proto`.
- Controller codegen:
  - `controller/Dockerfile`: `COPY ./observation_processor/proto /tmp/observation_processor/proto`; `protoc -Iscenescape_api/observation_processor/v1=/tmp/observation_processor/proto ... scenescape_api/observation_processor/v1/observation_processor.proto` → module `scenescape_api.observation_processor.v1.observation_processor_pb2` (+ `_pb2_grpc`).
  - `tests/sscape_tests/remote_projection/conftest.py`: same mapping.
- `.github/workflows/tracker-service.yml`: path filter `api/projection/**` → `observation_processor/proto/**`. Check other workflows for `api/projection`.
- `tracker/test/service/compose.yml`: config `projection-proto` → `observation-processor-proto` with file `../../../observation_processor/proto/observation_processor.proto`, mounted at `/protos/observation_processor.proto`. In `mocks/.../mock_*.py`, `grpc.protos_and_services("observation_processor.proto")`.
- Acceptance: tracker and controller images build; stubs import with `python3 -W error`.

#### B2. Tracker renames

Pipeline (local and remote processing; includes the names from #2148):

| Current                                                               | New                                                                           |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `DetectionProjector`                                                  | `ObservationProcessor`                                                        |
| `DetectionProjector::project()`                                       | `ObservationProcessor::process()`                                             |
| `ProjectedDetections`                                                 | `ProcessedObservations`                                                       |
| `CameraModelProjector`                                                | `CameraModelProcessor`                                                        |
| `RemoteProjector`                                                     | `RemoteObservationProcessor`                                                  |
| `ProjectorFactory`                                                    | `ObservationProcessorFactory`                                                 |
| `makeProjectorFactory()`                                              | `makeObservationProcessorFactory()`                                           |
| `TrackingWorker` `projector_` / constructor `projector`               | `processor_` / `processor`                                                    |
| `TimeChunkScheduler` `projector_factory_` / `projector_factory`       | `processor_factory_` / `processor_factory`                                    |
| locals `projected`, `projector`                                       | `processed`, `processor`                                                      |
| `RemoteProjectionConfig`                                              | `RemoteObservationProcessorConfig`                                            |
| `kDefaultRemoteProjectionTimeoutMs` / `kMaxRemoteProjectionTimeoutMs` | `kDefaultObservationProcessorTimeoutMs` / `kMaxObservationProcessorTimeoutMs` |
| "local projection" (comments, logs, test names, docs)                 | "local processing"                                                            |

Remote service:

| Current                      | New                                    |
| ---------------------------- | -------------------------------------- |
| `ProjectionClient`           | `ObservationProcessorClient`           |
| `ProjectionClientFactory`    | `ObservationProcessorClientFactory`    |
| `ProjectionFrame`            | `ObservationProcessorFrame`            |
| `ProjectionReply`            | `ObservationProcessorReply`            |
| `projectFrames()`            | `processFrames()`                      |
| `GrpcProjectionClient`       | `GrpcObservationProcessorClient`       |
| `makeGrpcProjectionClient()` | `makeGrpcObservationProcessorClient()` |
| `makeProjectionChannel()`    | `makeObservationProcessorChannel()`    |
| `connectProjectionService()` | `connectObservationProcessorService()` |

`RemoteMeasurement`, `ConditioningMode`, `parseConditioningMode`, `toString`, `toTrackerInputs`, `CoordinateTransformer` and the A3 `ZReference` helpers are kept.

- Files:
  - `detection_projector.{hpp,cpp}` → `observation_processor.{hpp,cpp}` (no clash with the generated `observation_processor.pb.h` / `.grpc.pb.h`)
  - `remote_projector.{hpp,cpp}` → `remote_observation_processor.{hpp,cpp}`
  - `grpc_projection_client.{hpp,cpp}` → `grpc_observation_processor_client.{hpp,cpp}`
  - `remote_projection_config.hpp` → `remote_observation_processor_config.hpp`
  - Tests: `observation_processor_test.cpp`, `remote_observation_processor_test.cpp`, `grpc_observation_processor_client_test.cpp`.
- Test names and fakes:
  - Suites: `CameraModelProjectorTest` → `CameraModelProcessorTest`, `RemoteProjectorTest` → `RemoteObservationProcessorTest`, `ProjectorFactoryTest` → `ObservationProcessorFactoryTest`, `GrpcProjectionClientTest` → `GrpcObservationProcessorClientTest`, `ProjectionChannelTest` → `ObservationProcessorChannelTest`.
  - Fakes: `CallbackProjector`, `FakeLocalProjector`, `FixedProjector`, `EmptyProjector` → `…Processor`; `FakeProjectionService` → `FakeObservationProcessorService`.
  - Helpers: `makeProjector` → `makeProcessor`, `make_projected` → `make_processed`, `ProjectFn` / `project_fn_` → `ProcessFn` / `process_fn_`.
  - Test names containing `LocalProjection` → `LocalProcessing`; `tracker_projection_ca_test` → `tracker_observation_processor_ca_test`.
- Config and schema:
  - `tracking.experimental_remote_projection` → `tracking.experimental_observation_processor`
  - `tracking.remote_projection_mode` → `tracking.observation_processor_mode`
  - `infrastructure.remote_projection` → `infrastructure.observation_processor`
  - Update the JSON-pointer constants and functions in `config_loader.{hpp,cpp}` (`load_observation_processor`, `apply_observation_processor_env`), `tracker/schema/config.schema.json` and `tracker/config/tracker.json`.
- Env vars (`tracker/inc/env_vars.hpp`): `TRACKER_EXPERIMENTAL_REMOTE_PROJECTION` → `TRACKER_EXPERIMENTAL_OBSERVATION_PROCESSOR`; `TRACKER_REMOTE_PROJECTION_{MODE,HOST,PORT,INSECURE,CA_CERT,TIMEOUT_MS}` → `TRACKER_OBSERVATION_PROCESSOR_{…}`.
- Metric: `tracker.remote_projection.failed_calls` → `tracker.observation_processor.failed_calls`; `kMetricObservationProcessorFailedCalls`; `Metrics::inc_observation_processor_failed_calls`.
- Logs: "Remote projection failed …; using local projection" → "Observation processor call failed …; using local processing"; "Experimental remote projection enabled/disabled" → "Experimental observation processor enabled/disabled".
- `tracker/docs/implementation.md`: heading "Why local projection runs on every frame" (from `40a0482fb`) → "Why local processing runs on every frame". Update the code comment that cites it.

#### B3. Controller renames

- Module `controller/src/controller/remote_projection.py` → `observation_processor.py`. Update imports in `ilabs_tracking.py`, `scene.py`, `controller-cmd` and the tests.

| Current                                                       | New                                                           |
| ------------------------------------------------------------- | ------------------------------------------------------------- |
| `RemoteProjector`                                             | `RemoteObservationProcessor`                                  |
| `RemoteProjector.project()` / `SceneProjection.project()`     | `process()`                                                   |
| `SceneProjection`                                             | `SceneObservationProcessor`                                   |
| `RemoteProjectionSettings`                                    | `RemoteObservationProcessorSettings` (mirrors the C++ config) |
| `GrpcProjectionClient`                                        | `GrpcObservationProcessorClient`                              |
| `get_projector()` / `_create_projector()` / `_projector`      | `get_processor()` / `_create_processor()` / `_processor`      |
| `Tracking.remote_projection`                                  | `Tracking.observation_processor`                              |
| `Scene._bindRemoteProjection()`                               | `Scene._bindObservationProcessor()`                           |
| `IntelLabsTracking._applyRemoteProjection()` (or its A5 name) | aligned, e.g. `_toTrackerReference()`                         |
| "local projection" (docstrings, logs, test names)             | "local processing"                                            |

`for_scene()`, `reset()`, `settings_from_env()`, `apply_measurement()` and `MEASUREMENT_SIZE` are kept. `MovingObject._projectBounds`, `projectToMap`, `project_to_map` and scene_common geometry are excluded (see [Rename](#rename-scope-and-names)).

- Env vars: `CONTROLLER_EXPERIMENTAL_REMOTE_PROJECTION` → `CONTROLLER_EXPERIMENTAL_OBSERVATION_PROCESSOR`; `CONTROLLER_REMOTE_PROJECTION_*` → `CONTROLLER_OBSERVATION_PROCESSOR_*`.
- CLI: `--experimental-remote-projection` → `--experimental-observation-processor` (dest `experimental_observation_processor`).
- Metric: `scenescape_controller_remote_projection_failed_calls` → `scenescape_controller_observation_processor_failed_calls`; `inc_observation_processor_failed_calls()` in `observability/metrics.py`.
- Logs: as in B2.

#### B4. Tests, mocks, compose and docs renames

- `tests/sscape_tests/remote_projection/` → `tests/sscape_tests/observation_processor/` (`test_observation_processor.py`, `conftest.py`).
- `tracker/test/service/test_remote_projection.py` → `test_observation_processor.py`.
- `mocks/projection/` → `mocks/observation_processor/` (`mock_observation_processor.py`, `MOCK_OBSERVATION_PROCESSOR_STATUS`, `MOCK_OBSERVATION_PROCESSOR_DELAY_MS`).
- Compose (`tracker/test/service/compose.yml`): service `mock-projection` → `mock-observation-processor`, profile `projection` → `observation-processor`, `TRACKER_OBSERVATION_PROCESSOR_*`. Align the mock port with the server default, 50052.
- Docs: tracker-service design doc, `tracker/docs/implementation.md`, how-to-configure-tracker (section title "Remote projection (experimental)" → "Observation processor (experimental)"), `controller.md`, how-to-enable-observability (metric names), `controller/Agents.md`, the `tests/requirements.txt` comment, and the A7 notes. "Local projection" becomes "local processing" throughout.
- Residual check, over the files #2148 and #2149 touch (base of #2148: `feature/prob-tracking-extracted-3d-R`). Every hit left must be one of the [Rename](#rename-scope-and-names) exclusions:

  ```
  BASE=$(git merge-base HEAD origin/feature/prob-tracking-extracted-3d-R)
  git grep -n -i -E "project(ed|or|ion|s)?\b|project(ed|or|ion)?_|projectFrames|ProjectDetections|REMOTE_PROJECTION|api/projection|projection\.proto" \
    -- $(git diff --name-only --diff-filter=d "$BASE" HEAD) \
    | grep -v -E "project_to_map|projectBounds|projectToMap|ProjectionToXY|bbox_projection_indices|PROJECT_|project\(|project_root|subproject"
  ```

  Review the remaining hits by hand: only pinhole-math prose may stay.

#### B5. Verification, commit and PR update

- Full matrix as in A8, including both image builds and the tracker service suite.
- The legacy bit-exact differential must stay empty: run `check_legacy.sh` again against the A1 baselines. The recorders use none of the renamed identifiers (`TrackingWorker` legacy constructor, `Track`, `Detection`, `DetectionBatch`, `Chunk`, `ObjectClassConfig`, `Camera`, `IntelLabsTracking`, `MovingObject`, `ATagObject`), so they should compile unchanged; if one does not, adjust only the renamed identifier, never the recorded inputs. They are still not committed.
- Commit as one rename commit, or one per service if large: "Tracker, Controller: rename projection to observation processing".
- Update the PR title and description, keeping the repository PR template. Mention the new env vars and CLI flag, the contract location and the plaintext server note.

#### C1. Follow-ups

- Server TLS: the server serves plaintext only; decide a TLS rollout or document `*_INSECURE=true` for the experimental phase.
- End-to-end evaluation in experimental mode with a real server: Tracker Evaluation black-box runs, base vs experimental, for HOTA, IDF1, DIST_T and z/vz statistics.
- If planar z/vz noise in experimental mode bothers consumers: options are a per-category constant height for planar inputs, or smoothing; each needs a new decision.
- One z reference in legacy mode: option U applies only with the observation processor, so in legacy mode a track fed by a pixel camera (ground point) and a 3D sensor (box centre) still fuses a midpoint height and gets spurious `vz` when sensors alternate. Association no longer splits on it: #2109 gates z only when the track and the detection both have `zMeasured` (`dec3b387f`). Options and status: [post-review plan, follow-up work](prob-tracking-post-review-plan.md#follow-up-work).
