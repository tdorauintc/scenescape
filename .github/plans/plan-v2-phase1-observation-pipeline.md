<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Implementation Plan: Scenescape V2 Phase 1 — Controller Observation Pipeline (Stairs-first)

- **Author(s)**: [Sarat Poluri](https://github.com/spoluri)
- **Date**: 2026-10-22
- **Status**: Implemented (Stairs-first); live-verified; follow-ons for mesh frame, axis-aware sizing, `project_to_map`, and Σ→R shipped
- **Source algorithms**: [`scenescape-v2-architecture`](https://github.com/intel-sandbox/scenescape-v2-architecture) (`algorithms/frustum-gaussian`, `algorithms/amodalreasoner`)
- **Related**: [ADR-0017](../../docs/adr/0017-probabilistic-tracking-association.md), [plan-probabilistic-tracking.md](./plan-probabilistic-tracking.md), [debug-z-offset-stairs.md](./debug-z-offset-stairs.md)
- **Commits** (`feat/full-v2-tracking-pipeline`): `682c2a79` (initial), `115c2362` (mesh→world), `1dc10f13` (Σ→R), `9530f8e0` (axis-aware frustum), `e33657c1` (`project_to_map` mesh foot→CoM), `f0ae67f2` (asset `axis_aware_sizing`)

This plan is the **as-built** record for Phase 1: tasks, integration points, Stairs verification, and post-debug follow-ons. Full architecture lives in the v2-architecture repo; ADR-0017 covers the Mahalanobis/UKF association layer reused here. Z-offset bisect evidence lives in [debug-z-offset-stairs.md](./debug-z-offset-stairs.md).

---

## Naming

**This plan’s “Phase 1”** is the end-to-end observation path:

```text
detections → frustum_gaussian → observation_conditioning (amodal) → probabilistic tracking
```

In `scenescape-v2-architecture` those stages are labeled Phases 1 / 2 / 3a–3b. Packages keep those names; only the vendored paths below changed.

**Decisions locked in (and shipped):**

- Vendored into [`scene_common/src/frustum_gaussian`](../../scene_common/src/frustum_gaussian) and [`scene_common/src/observation_conditioning`](../../scene_common/src/observation_conditioning)
- **Stairs-only** gate; legacy floor/ray projection remains the default for all other scenes

---

## As-built data flow

```mermaid
flowchart LR
  det[MQTT detections] --> create[_createMovingObjectsForDetection]
  create --> gate{uses_observation_conditioning?}
  gate -->|no| track[IntelLabsTracking]
  gate -->|yes| pipe[ObservationPipeline.apply]
  pipe --> fg["frustum (axis_aware from asset)"]
  fg --> oce[AmodalReasoner.generate]
  oce --> p2m{"project_to_map?"}
  p2m -->|yes| foot["depth-map foot + half-height CoM"]
  p2m -->|no| cent[frustum/amodal centroid]
  foot --> set[sceneLoc / has_measured_z / observation_sigma]
  cent --> set
  set --> track
  track --> r["measurement_covariance from Σ"]
  r --> mqtt[scenescape/data/scene/.../person]
```

Hook site: [`Scene`](../../controller/src/controller/scene.py) after object creation, before `_finishProcessing` — not inside `MovingObject.mapObjectDetectionToWorld`. On Stairs, conditioning **overwrites** the legacy world location; on failure or missing mesh/reasoner, the legacy projection is left unchanged.

**MQTT contract:** `translation` is always the geometric / mass center (CoM). The 3D UI places assets at `translation` with no `project_to_map` / axis-aware branching.

---

## 1. Vendored packages (`scene_common/src/`)

### `frustum_gaussian/`

| Item | As built |
|------|----------|
| Runtime kernel | Pure NumPy in [`_pure.py`](../../scene_common/src/frustum_gaussian/_pure.py); public API in [`__init__.py`](../../scene_common/src/frustum_gaussian/__init__.py) |
| C++ / pybind | Sources kept under [`cpp/`](../../scene_common/src/frustum_gaussian/cpp/) for a future scikit-build; **not** built in the controller image yet |
| SceneScape bridge | `from_scenescape_detections`, `transform_to_world_batch`, `PERSON_SHAPE_PRIOR` (~0.55×0.55×1.70 m) |
| Axis-aware sizing | Default **on**: BB width↔`μ_x`, height↔`μ_z`. Off → orientation-averaged `dim_est`. Per-detection via `axis_aware` / detection dict `axis_aware_sizing` (Python + C++) |
| Provenance | `NOTICE`, `README.md`, `ALGORITHM.md`, `AGENTS.md` |

Import: `import frustum_gaussian as fg`.

### `observation_conditioning/`

| Item | As built |
|------|----------|
| Public API | Lazy `from observation_conditioning import AmodalReasoner` (avoids open3d at install time in common-base) |
| Modules | `amodal_reasoner.py`, `intersection_map.py`, `constants.py` |
| Imports | Package-relative (`from .constants import ...`), not `from src....` |
| Provenance | `NOTICE`, `README.md`, `amodal_reasoner_algorithm.md` |

### Packaging / image install

- Sibling packages under `scene_common/src/` are picked up by [`scene_common/src/setup.py`](../../scene_common/src/setup.py) (`find_packages`) when the common-base image installs from that tree.
- Controller runtime explicitly copies both packages from the builder stage in [`controller/Dockerfile`](../../controller/Dockerfile):
  - `site-packages/frustum_gaussian`
  - `site-packages/observation_conditioning`

---

## 2. Controller observation path

### Gate

[`sceneUsesObservationConditioning`](../../controller/src/controller/observation_pipeline.py) — hard allow-list:

```python
OBSERVATION_CONDITIONING_SCENE_NAMES = frozenset({"Stairs", "Basketball"})
```

Exposed on the scene as `Scene.uses_observation_conditioning`. No scene-config / UI flag yet.

### Adapter: `ObservationPipeline`

New module: [`controller/src/controller/observation_pipeline.py`](../../controller/src/controller/observation_pipeline.py).

Wired in [`scene.py`](../../controller/src/controller/scene.py):

- `self.observation_pipeline = ObservationPipeline(self)` on construct
- After `_createMovingObjectsForDetection`, if gated: `self.observation_pipeline.apply(objects, camera, when)`
- `invalidate()` on `updateScene` and when cameras are removed

### Per-camera `AmodalReasoner` cache

Built lazily in `_reasoner_for_camera`:

- Mesh: **world-frame** tensor from `_world_mesh_tensor()` — applies scene `mesh_translation` / `mesh_rotation` / `mesh_scale` (unit default; never map `Scene.scale`) to `map_triangle_mesh` (H2 fix; see [debug-z-offset-stairs.md](./debug-z-offset-stairs.md))
- Intrinsics: `fx,fy,cx,cy` + resolution from camera pose
- Extrinsics: `camera.pose.pose_mat` (camera→world)
- World-up: `[0, 0, 1]` (`DEFAULT_WORLD_UP`)
- Cache key: rounded intrinsics/resolution/pose + mesh pose key + `id(map_triangle_mesh)`
- `num_layers=4`

### Object-library knobs (per asset / category)

| Asset field | Default | Effect on Stairs observation path |
|-------------|---------|-----------------------------------|
| `axis_aware_sizing` | `True` | Passed into frustum as `axis_aware` (width/height vs orientation-averaged `dim_est`) |
| `project_to_map` | `False` | After frustum/amodal: BB **foot** → depth-map mesh hit, then lift half `size_z` (else prior `μ_z/2`) along world-up → **CoM** `translation` |

Wired: Manager model/API/UI → `Tracking` → `MovingObject` → `ObservationPipeline.apply`. Docs: [how-to-define-object-properties.md](../../docs/user-guide/other-topics/how-to-define-object-properties.md). Migration: `0006_asset3d_axis_aware_sizing`.

### Per-frame steps (Stairs)

1. Collect pixel BBs from each `MovingObject.boundingBoxPixels`; stamp `axis_aware_sizing` from the asset
2. `fg.from_scenescape_detections(..., shape_prior=fg.PERSON_SHAPE_PRIOR)` → camera-frame Gaussians
3. `fg.transform_to_world_batch(cam_obs, pose_mat)`
4. Remap batch to amodal `gaus_rays` with `mu` = **camera origin in world** (tiled), plus world-frame `ray` / depth / `Sigma`
5. `AmodalReasoner.generate(gaus_rays)` → `updated_depth`, `updated_var` (or frustum-only / skip when mode/`reasoner` dictates)
6. Centroid: `mu + ray * updated_depth`
7. If `project_to_map`: replace with depth-map **foot** hit + half-height CoM lift (MQTT stays CoM; UI unchanged)
8. Write `orig_point`, `location`, `vectors`; `has_measured_z = True`
9. Attach `observation_depth_var` and `observation_sigma` (3×3 world Σ)

Fallback: any exception or missing reasoner/mesh → log and keep legacy projection for that frame.

### Probabilistic tracking

- No information-form multi-camera fuser (arch Phase 3a) in this slice
- Consumer remains `TimeChunkedIntelLabsTracking` / `IntelLabsTracking` + ADR-0017 Mahalanobis
- Stairs deployment requires `use_tracker: true`
- **Σ → R:** `ilabs_tracking.measurement_covariance_from_observation` embeds `observation_sigma` in the 7×7 `measurement_covariance` (x,y,z block) for UKF / association (ADR Phase 3 path started; see [plan-probabilistic-tracking.md](./plan-probabilistic-tracking.md))

---

## 3. Tests

| Suite | Path | Coverage |
|-------|------|----------|
| Frustum smoke | [`tests/sscape_tests/frustum_gaussian/`](../../tests/sscape_tests/frustum_gaussian/) | `project_frustum_batch`, `from_scenescape_detections`, `transform_to_world_batch`, empty batch, axis-aware vs averaged depth |
| Gate / mesh pose / foot→CoM | [`tests/sscape_tests/observation_pipeline/`](../../tests/sscape_tests/observation_pipeline/) | Stairs allow-list; mesh→world pose; depth-map foot project + half-height helpers |
| Asset CRUD | [`tests/functional/test_object_crud_api.py`](../../tests/functional/test_object_crud_api.py), UI object/3D asset CRUD | `axis_aware_sizing` field present |

---

## 4. Live Stairs verification (done)

Environment: empty DB, Stairs imported, cam1/cam2 DLStreamer, MQTT tracks.

Checked:

1. Rebuilt controller image; `scene` container recreated with frustum + observation_conditioning present in site-packages
2. Logs: `ObservationPipeline: built AmodalReasoner for …` and conditioned-detection debug without hard failures
3. MQTT `scenescape/data/scene/<stairs_uid>/person` — person tracks with measured Z / multi-camera `visibility` (`stair-cam-1` / `stair-cam-2`)
4. Conditioning path active only for scene name `Stairs`

---

## 5. Out of scope (next phases)

- General scene config flag / UI toggle for enabling observation conditioning (still Stairs hard-gate)
- Information-form multi-camera fuser (arch Phase 3a)
- Completing ADR Phase 3 default flip / full eval of per-measurement R (Σ is now written into `measurement_covariance`; see probabilistic-tracking plan)
- Building the frustum C++ extension in the Docker image (numpy path is production for Phase 1; C++ sources keep `axis_aware` in sync)
- Tracker-service C++ port of frustum/amodal
- Dynamic-mesh OCE (amodal Phase 2)
- Amodal “project onto support surface” for underestimated depth when no occluder/wall bound fires (depth-map foot path covers the `project_to_map` case only)

---

## Key files (shipped)

| Path | Role |
|------|------|
| [`scene_common/src/frustum_gaussian/**`](../../scene_common/src/frustum_gaussian) | Vendored frustum + numpy runtime |
| [`scene_common/src/observation_conditioning/**`](../../scene_common/src/observation_conditioning) | Vendored amodal / OCE |
| [`scene_common/src/setup.py`](../../scene_common/src/setup.py) | Installs sibling packages via `find_packages` |
| [`controller/Dockerfile`](../../controller/Dockerfile) | COPY both packages into runtime image |
| [`controller/src/controller/observation_pipeline.py`](../../controller/src/controller/observation_pipeline.py) | Gate, mesh→world, frustum/amodal, optional `project_to_map` foot→CoM |
| [`controller/src/controller/scene.py`](../../controller/src/controller/scene.py) | Stairs hook + invalidate |
| [`controller/src/controller/ilabs_tracking.py`](../../controller/src/controller/ilabs_tracking.py) | `observation_sigma` → 7×7 `measurement_covariance` |
| [`manager/.../Asset3D`](../../manager/src/manager/models.py) | `project_to_map`, `axis_aware_sizing` |
| [`tests/sscape_tests/frustum_gaussian/`](../../tests/sscape_tests/frustum_gaussian/), [`tests/sscape_tests/observation_pipeline/`](../../tests/sscape_tests/observation_pipeline/) | Smoke / gate / mesh / axis-aware tests |

---

## Task checklist

| ID | Task | Status |
|----|------|--------|
| vendor-frustum | Vendor frustum-gaussian (numpy runtime + cpp sources retained); install via scene_common + controller Dockerfile COPY | Done |
| vendor-oce | Vendor amodalreasoner as `observation_conditioning`; package-relative imports; lazy `AmodalReasoner` | Done |
| controller-adapter | `ObservationPipeline` + Stairs-only gate; per-camera `AmodalReasoner` cache + invalidate | Done |
| wire-detections | Stairs: frustum → world → OCE → `sceneLoc` / `has_measured_z` (+ Σ attrs) into IntelLabsTracking | Done |
| tests-smoke | `tests/sscape_tests/frustum_gaussian` + `observation_pipeline` gate tests | Done |
| verify-stairs | Rebuild controller; Stairs live verify (MQTT tracks + conditioning logs) | Done |
| mesh-world-frame | Transform scene GLB by mesh pose before `DepthMap` / amodal (H2) | Done |
| sigma-to-R | Pass `observation_sigma` through `to_rv_object` as measurement R | Done |
| axis-aware-frustum | Axis-aware width/height sizing; asset `axis_aware_sizing` (default on) | Done |
| project-to-map-mesh | Asset `project_to_map`: depth-map foot + half-height CoM (stable MQTT/UI contract) | Done |
