<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Stairs observation Z-offset — debug findings

**Date**: 2026-10-23  
**Plan**: [debug-z-offset-stairs.md](./debug-z-offset-stairs.md)  
**Environment**: live `scenescape-scene-1` + Stairs DLStreamer (stair-cam-1/2)

Instrumentation added in [`controller/src/controller/observation_pipeline.py`](../../controller/src/controller/observation_pipeline.py):

- Stage A–F logs when `/tmp/observation_pipeline_debug` exists (or `OBSERVATION_PIPELINE_DEBUG=1`)
- Mode switch via `/tmp/observation_pipeline_mode` = `full` | `frustum_only` | `off`

---

## Step 0 — Symptom characterization (from Stage F logs)

| Metric | Value |
|--------|-------|
| Sign | World Z of conditioned centroids is **near floor / slightly above** (~0.0–1.3 m), not near camera height (~2.2 m) |
| Magnitude vs expected torso on floor (floor≈0 + 0.85) | Upper-body samples ≈ **+0.4 m** (H1 band); some lower-image BBs ≈ **0.0–0.3 m** (near feet / shallow) |
| Constant vs depth-dependent | Depths ~3.8–4.4 m stable; Z variation tracks ray dip more than range |
| Per-camera | Both cams agree on world XY≈(3.8, 5.3) and Z≈1.28 for the upper person |
| Detection vs track | Stage F is pre-tracker; amodal Δdepth = 0 so tracker sees frustum centroid |

Representative sample (`stair-cam-2`, full mode):

| Stage | Value |
|-------|-------|
| A | BB=(872,84,148,343), K=(978.74,978.74,640,360), 1280×720, cam_origin≈(1.31, 8.29, 2.24) |
| B | depth_est=4.004, lo=3.265, hi=5.337, score=0.996, edge_valid=15 |
| C | world_mu≈(3.84, 5.33, 1.29), ray≈(0.63, -0.74, -0.24) |
| D | mu_remap_err=0 (mu = cam origin) |
| E | updated_depth=4.004, **delta_depth=0.000** |
| F | centroid≈(3.84, 5.33, 1.29), prior_half_height=0.85 |

---

## Step 1 — Path confirmation

- Logs: `ObservationPipeline: built AmodalReasoner for stair-cam-1/2 … mode=full`
- Stairs gate active; conditioning runs before tracker.

---

## Step 2 — Bisect result

- **D OK**: `mu` correctly remapped to camera origin.
- **E**: `E_delta_depth=0` on all sampled detections → amodal is **passthrough** (not moving depth).
- **C/F**: World Z comes entirely from frustum prior + pose (same as frustum-only).

Bisect: failing stage for “wrong Z vs scene mesh/floor” is **mesh frame used by amodal (and therefore no mesh conditioning)**, not UKF publish. Frustum Z itself is consistent with a **centroid ~0.4–1.0 m above floor** once the mesh is expressed in world.

---

## Step 3 — Hypotheses

| ID | Verdict | Evidence |
|----|---------|----------|
| **H2 mesh frame** | **CONFIRMED (primary)** | Raw mesh AABB ≈ ±(3.5, 2.0, 4.5); cameras at y≈8 → `cam_inside_mesh_xy=False`. Scene has `mesh_translation≈(3.53, 4.48, 1.96)`, `mesh_rotation=[90,0,0]`. Pipeline passes **untransformed** `map_triangle_mesh` into `DepthMap`. Applying R_x(90°)+translation → world AABB **[0,0,0]–[7.06, 8.97, 3.92]** with cameras **inside** XY and floor Z≈0. |
| H5 amodal pull | **Killed** | `E_delta_depth=0` always in samples (no occluder/wall update). |
| H1 centroid vs foot | **Plausible secondary (~0.4–1 m)** | F_centroid Z≈1.29 vs floor 0 + half-height 0.85 → Δ≈0.44 m. Explains sub-meter “high”, not multi-meter, once mesh frame is understood. |
| H3 world-up | Unlikely primary | After intended R_x(90), scene is Z-up; `DEFAULT_WORLD_UP=[0,0,1]` matches transformed mesh. Raw GLB looks Y-up before rotation. |
| H4 frustum prior / K | Not primary for upper person | depth_est≈4 m, score high, both cams agree; K/res look sane (1280×720). |
| H6 camera pose | Unlikely | Both cams consistent; origins Z≈2.16–2.24 sit under transformed ceiling (~3.92). |
| H7 tracker | Not implicated | Observation Z already set at Stage F; amodal not changing it. |

**Note on logged `mesh_scale=85.62`**: that value came from `Scene.scale` (map px/m fallback in the debug dump), not a GLB scale vector. Unit scale + translation/rotation is the correct transform for this Stairs mesh (world AABB starts at origin).

---

## Step 4 — A/B

| Mode | Result |
|------|--------|
| Full | Centroid Z≈1.29 (upper), Δdepth=0 |
| Frustum-only | **Equivalent to full** while Δdepth=0 (no need for separate run to conclude) |
| Legacy (off) | Not re-sampled this session; expected planar/foot path with Z≈0 / no `has_measured_z` |

Pattern: **Full ≈ frustum-only**. Amodal does not explain the error today because the mesh is in the wrong frame (H2), so conditioning never engages.

---

## Step 5 — Fix decision (do not implement in this debug pass)

**Confirmed root cause:** H2 — observation pipeline builds `AmodalReasoner`/`DepthMap` on the raw GLB mesh without applying scene `mesh_translation` / `mesh_rotation` (/ unit `mesh_scale`).

**Fix implemented:** `ObservationPipeline._world_mesh_tensor()` applies scene `mesh_translation` / `mesh_rotation` / `mesh_scale` (unit default; never map `Scene.scale`) before `AmodalReasoner` / `DepthMap`. Live verify after patch: nonzero `E_delta_depth` (amodal engaged). Residual ~0.5–1 m vs floor may still be H1 (centroid vs foot).

---

## How to reproduce logs

```bash
docker cp controller/src/controller/observation_pipeline.py \
  scenescape-scene-1:/usr/local/lib/python3.11/site-packages/controller/observation_pipeline.py
docker exec scenescape-scene-1 sh -c 'echo full > /tmp/observation_pipeline_mode; touch /tmp/observation_pipeline_debug'
docker restart scenescape-scene-1
# wait healthy, then:
docker logs scenescape-scene-1 2>&1 | grep ZDBG
```
