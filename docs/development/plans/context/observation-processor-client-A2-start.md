# Legacy baselines for the M1 bit-exact check: context for a new session

This document accompanies the plan [prob-tracking-observation-processor-client-plan.md](../prob-tracking-observation-processor-client-plan.md)
(repo `scenescape-prob-tracking-review`, branch `tdorau/feature/prob-tracking-review`; the plan is committed up to A1 done in `68386cbfe`).
It is the context for a new session that starts at task A2. The recorders, harness scripts and baselines it describes are
**local-only artifacts that are never committed**, and the paths below are specific to this machine. Task A1 of the plan is done;
A8 and B5 reuse what is described here.

## 1. What the baselines are for

- The plan feeds robot_vision centre-of-mass positions and publishes the footprint base **only in experimental mode**.
  In legacy mode (observation processor off) the Tracker service and the Scene Controller must publish output that is
  **bit-exact** with the PR base.
- Two recordings of that legacy output were taken on the PR base `b4c1e2e9d36dcca1f1c4b1f68a1dd31cb1ca0761`
  (`tdorau/prob-tracking-stp-tracker-refactor`, #2148). After the Phase A changes (A8) and the Phase B renames (B5), the same recorders run on the PR branch and the
  output must be byte-identical.
- The PR branch is `tdorau/prob-tracking-stp-client-side` (#2149), checkout
  `/home/tdorau/repos/scenescape-prob-tracking-3d-R`, at `c3ca618f1`: `fc3a0dc02` (pushed to `origin`) plus one local, not pushed,
  commit `TEMPORARY: add the observation processor contract from the server branch`. That commit adds
  `observation_processor/proto/observation_processor.proto`, byte-identical to `origin/ITEP-98099_observation_processor_service`; nothing uses it
  until Phase B1. The working tree is clean.

## 2. Where everything is

Harness folder (outside every repo, never commit anything from it):
`/home/tdorau/.copilot/session-state/c3bad055-7ac0-4a49-b445-2bb1f2f4bb1e/files/m1-harness/`

| File                       | Purpose                                                                                        |
| -------------------------- | ---------------------------------------------------------------------------------------------- |
| `base_py.txt`              | Controller baseline, 19,689 lines, sha256 `2ba368196a2ad975…`                                  |
| `base_cpp.txt`             | Tracker baseline, 3,101 lines, sha256 `00cfd935419872c2…`                                      |
| `py_record.py`             | Controller recorder: `python py_record.py <tree> <out>`                                        |
| `legacy_recorder_test.cpp` | Tracker recorder (gtest `LegacyRecorder.RecordsPublishedTracks`, enabled by `M1_RECORD_OUT`)   |
| `tracker_harness.sh`       | `install` / `uninstall` the Tracker recorder in a tree (copies the file, edits the test CMake) |
| `check_legacy.sh [tree]`   | Re-runs both recorders on a tree and compares with the baselines                               |
| `README.txt`               | Short pointer to this document                                                                 |

Local helper tree: `/tmp/m1-base` (a git worktree at the base commit, with `tracker/build-debug` built with
`-DBUILD_TESTS=ON -DBUILD_RV_TESTS=OFF`). `/tmp` is volatile; section 6 recreates it. It is only needed to **re-record**
the baselines, not to run the check.

## 3. Running the check (A8, B5)

```bash
H=/home/tdorau/.copilot/session-state/c3bad055-7ac0-4a49-b445-2bb1f2f4bb1e/files/m1-harness
$H/check_legacy.sh                      # PR checkout; or pass another tree
```

Expected output (about 1 minute with an up-to-date Tracker build):

```
frames=1500 rv_inputs=7691 published_objects=10498
[  PASSED  ] 1 test.
CONTROLLER legacy output: bit-identical to base
TRACKER legacy output: bit-identical to base
```

What the script does:

1. Runs `py_record.py` on the tree (needs `tests/.venv` of the PR checkout; proxy variables are unset) and writes `new_py.txt`.
2. Installs the Tracker recorder into the tree (`tracker/test/unit/legacy_recorder_test.cpp` and one line in
   `tracker/test/unit/CMakeLists.txt`), builds `tracker_tests` in `<tree>/tracker/build-debug`, runs the recorder with
   `M1_RECORD_OUT=…/new_cpp.txt`, and **uninstalls the recorder on exit** (trap), also on failure.
3. `cmp`s `new_py.txt` / `new_cpp.txt` against `base_py.txt` / `base_cpp.txt`.

The recorders drive the **legacy** path only (no observation processor); the experimental behaviour is covered by the new unit and
service tests of A2–A6.

Rules:

- Never commit the recorders, the baselines or the CMake registration. After the script, `git status` must show only your real changes.
- The Tracker build directory must exist (`make -C tracker build-debug` or the conan/cmake commands in section 6).
- A non-empty difference means the legacy path changed. Locate it with `diff base_cpp.txt new_cpp.txt | head`
  (Tracker lines are `chunk <n> <scene>/<category> …` followed by `  track …` lines) or
  `diff base_py.txt new_py.txt | head` (Controller lines are `frame <n>`, `in …` robot_vision inputs and `out …` published
  objects). `in` lines differing means the input conversion leaked into legacy mode; `out` lines differing means the output conversion did.

## 4. What the recorders do

Controller (`py_record.py`): real `IntelLabsTracking` (real robot_vision, production settings from `IntelLabsTracking.__init__`),
tracker thread not started, `tracker.uuid_manager.scene_id` set, `remote_projection` unset. A `Spy` wrapper records every
robot_vision input and delegates to the real tracker. 1,500 frames at 15 fps from `t0 = 1_700_000_000`:

- `n % 3 == 0`: `trackCategory()` with 4 planar `MovingObject` pixel boxes, one `ATagObject` (hover z) and, on even frames, a 3D `translation` object.
- otherwise `trackCategoryBatched()` with two cameras: planar boxes (0–4 per camera) plus a 3D object on cam-1; every 50th such frame is empty.
- Records per input: `in x y z length width height yaw zm=<zMeasured> R=<-|set>`; per published object:
  `out rv=<id> x y z vx vy vz size×3 rotation×4`; all numbers as `float.hex`.
- Result: 7,691 inputs (1,230 `zMeasured`, 1,268 planar with z ≠ 0), 10,498 published objects, 61 track IDs, longest track 1,494 frames, 7,509 published objects with z exactly 0 (planar tracks).

Tracker (`legacy_recorder_test.cpp`): legacy `TrackingWorker` constructor, fixed `ClockFn`, queue capacity 2, one chunk
enqueued at a time and `processed_count()` awaited, 300 chunks × 2 scopes, `mt19937(2149)`:

- Scope A `scene-A/person` (default `ObjectClassConfig`): cam-1 planar boxes (3) plus a 3D detection from each camera on even chunks (size, rotation every 4th chunk).
- Scope B `scene-B/vehicle` (`footprint_half = 0.4`, `rotation_from_velocity = true`): cam-1 planar boxes (4) only.
- Every 50th chunk is empty. Track IDs (UUIDs) are normalised by first appearance; every value is `{:a}` hexfloat, including the association window.
- Result: scope A 1,361 track lines (7 IDs, 855 with z = 0, the rest with measured z up to 4.44 m), scope B 1,140 track lines (4 IDs, all z = 0, |vz| = 0).

Both recorders were run three times on the base with byte-identical results. Both were also run on the PR head `fc3a0dc02`:
both outputs were bit-identical to the base, i.e. legacy mode is already bit-exact today.

## 5. Pitfalls found while building the harness (relevant to every new test that feeds pixel boxes)

1. **Pixel boxes must end below the horizon.** The camera model intersects the box foot with the ground. The test cameras
   (3 m high, rotation `[-90, 0, 0]`, `cy = 360`) project a box with `y + height < cy` to **kilometres** away.
   Objects built from such boxes "move" at tens of m/s and never become reliable tracks (the first recordings were useless
   for this reason). Use e.g. `{x, 400, 55, 150}` (foot 190 px below the horizon, about 14 m from the camera).
   Stationary boxes are unaffected, which is why the old stationary service-test boxes (`BBOX`, `GRID_BOXES`) and the old
   worker-test box `{10, 20, 50, 100}` still pass. The plan's A2 and A6 carry the same rule.
2. **The Tracker recording uses planar boxes from `cam-1` only.** Planar boxes of the two differently posed cameras land on
   overlapping world positions, the Hungarian assignments flip between frames and no track becomes reliable. Multi-camera
   fusion in the Tracker recording is covered by 3D detections from both cameras; the multi-camera planar path is covered by the
   Controller recording only.
3. A track needs `ceil(15 fps × 1.0 s) = 15` tracked frames to become reliable, so tests need more than 15 chunks.
4. `IntelLabsTracking(…, effective_object_update_rate)` needs an `int` for the rate; detections need an `id`; `ATagObject` needs
   `tag_family` and `tag_id`.

## 6. Environment and recreating the helper tree

Assumptions baked into the baselines (re-record if any of these change):

- Same machine and toolchain: gcc/libm, OpenMP, numpy 2.2.6, Python 3.12, timezone CET (the Controller path calls
  `datetime.fromtimestamp()`).
- Python recorder imports `robot_vision` from the PR checkout's venv
  (`/home/tdorau/repos/scenescape-prob-tracking-3d-R/tests/.venv/lib/python3.12/site-packages/robot_vision`), not from the tree being tested.
  The Tracker recorder uses the `robot_vision` source of the tree being built (`controller/src/robot_vision`, added via
  `add_subdirectory`). If robot_vision changes in either place, re-record.

Recreate `/tmp/m1-base` and the Tracker build (only needed to re-record):

```bash
git -C /home/tdorau/repos/scenescape-prob-tracking-3d-R worktree add /tmp/m1-base b4c1e2e9d36dcca1f1c4b1f68a1dd31cb1ca0761
H=/home/tdorau/.copilot/session-state/c3bad055-7ac0-4a49-b445-2bb1f2f4bb1e/files/m1-harness
$H/tracker_harness.sh /tmp/m1-base install
cd /tmp/m1-base/tracker
conan install . --output-folder=build-debug --build=missing -s build_type=Debug -c tools.cmake.cmaketoolchain:generator=Ninja
cmake --preset conan-debug -DBUILD_TESTS=ON -DBUILD_RV_TESTS=OFF -DGIT_COMMIT=m1base
cmake --build build-debug --target tracker_tests -j
. build-debug/conanrun.sh
M1_RECORD_OUT=$H/base_cpp.txt ./build-debug/test/unit/tracker_tests --gtest_filter='LegacyRecorder.*'
env -u http_proxy -u https_proxy /home/tdorau/repos/scenescape-prob-tracking-3d-R/tests/.venv/bin/python $H/py_record.py /tmp/m1-base $H/base_py.txt
$H/tracker_harness.sh /tmp/m1-base uninstall
```

Run each recorder twice and `cmp` the outputs before trusting a new baseline.

The recorders need no change for Phase B: they use none of the renamed identifiers (`TrackingWorker` legacy constructor,
`Track`, `Detection`, `DetectionBatch`, `Chunk`, `ObjectClassConfig`, `Camera`, `IntelLabsTracking`, `MovingObject`, `ATagObject`).
If a compile error appears, adjust only the renamed identifier, never the recorded inputs.

## 7. State to continue from

- Plan: A1 done; next A2 (Tracker tests, red). Phase A is test-first: failing tests first, then implementation.
- A2 starting points in the PR checkout (line numbers are approximate):
  - `tracker/test/unit/tracking_worker_test.cpp`: fixture `TrackingWorkerTest` (`make_test_cameras()`: `cam-1`, 3 m high, rotation `[-90, 0, 0]`, intrinsics 905/905/640/360;
    `get_processed_count_wait()`); `CallbackProjector` (around line 1804) is the fake projector for the injected-projector constructor, used by the tests around lines 1876 and 1919.
  - `tracker/test/unit/time_chunk_scheduler_test.cpp`: `Dispatch_UsesProjectorFactoryForNewWorkers` (around line 394) with a local `FixedProjector`.
  - `tracker/test/unit/remote_projector_test.cpp`: `expectRemote()` (around line 200) asserts `z == 0.0` with the message "centre z lowered by half the height"; A2 changes it to `kHeight / 2.0`. Helpers: `denseR()`, `FakeLocalProjector`, `FakeClient`.
  - New test file for A2: `tracker/test/unit/z_reference_test.cpp`, testing the helpers of `tracker/inc/z_reference.hpp` that A3 adds (register the test in `tracker/test/unit/CMakeLists.txt`).
  - Remember the pixel-box rule of section 5: boxes in the new tests must end below the horizon, e.g. `{600, 420, 55, 150}` with the worker-test camera.
- Build and run the Tracker unit tests with `make -C tracker test-unit` (about 1 minute); iterate with
  `cmake --build tracker/build-debug --target tracker_tests -j && . tracker/build-debug/conanrun.sh && tracker/build-debug/test/unit/tracker_tests --gtest_filter='<Suite>.*'`.
- Copilot replies for threads 1, 3 and 4 are in the plan (the user posts them). Threads 2 and 5 are handled by A9 after A8.
- Local images with their own tags (safe to keep): `intel/scenescape-tracker:stp-eager` (Tracker code of `fc3a0dc02`),
  `intel/scenescape-tracker:stp-latency` (code before the connect-at-startup fix), `intel/scenescape-controller-stp-pins:check`.
  Rebuild with a new tag for new code: `docker build --target runtime --build-arg BUILD_TYPE=Release -t intel/scenescape-tracker:<tag> -f tracker/Dockerfile .` Tracker service tests:
  `cd tracker/test/service && VERSION=<tag> .venv/bin/pytest -v` (16 tests; unset `TRACKER_MQTT_*`).
- Verification commands for the whole plan are in the plan's "Verification commands and environment" section; the Python suites
  need `make init-secrets` once and proxy variables unset.
