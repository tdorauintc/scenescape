# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Observation pipeline: frustum → amodal → optional multi-view triangulation.

Converts 2D camera detections into world points for the IntelLabs tracker.
Gated scenes (Stairs, Basketball); others keep the legacy path.

Stages (camera-only; other modalities already carry metric range):

1. **Frustum Gaussian** — monocular BB + shape prior → depth / ray
2. **Amodal conditioning** — per-camera mesh truncation of the depth Gaussian
3. **Multi-view triangulation** (opt-in cross-observation conditioning) —
   when another camera recently saw the same category, replace the
   monocular centroid with the skew-ray midpoint. Kept in the toolbox;
   off by default until association/baseline are strong enough (short
   baselines can slide free-moving objects along the camera ray). Helpers
   live in ``observation_conditioning``.

When an object-library asset has ``project_to_map`` enabled, the BB foot is
snapped to the mesh then lifted to CoM (skips triangulation for that det).

Debug (optional Z-offset isolation):
  OBSERVATION_PIPELINE_DEBUG=1     — log Stage A–F fields (rate-limited)
  OBSERVATION_PIPELINE_MODE=full|frustum_only|off
      full          — frustum + amodal (default)
      frustum_only  — skip amodal; use depth_est as updated_depth
      off           — disable conditioning (legacy path)
  OBSERVATION_TRIANGULATION=1      — enable stage 3 (off by default)
  Or write mode to /tmp/observation_pipeline_mode and touch
  /tmp/observation_pipeline_debug.
"""

from __future__ import annotations

import os
from collections import deque

import numpy as np

from scene_common import log

# Hard-gate for Phase 1 verification (Stairs + Basketball demos).
OBSERVATION_CONDITIONING_SCENE_NAMES = frozenset({"Stairs", "Basketball"})

# Default world-up for SceneScape meshes (Z-up).
DEFAULT_WORLD_UP = np.array([0.0, 0.0, 1.0], dtype=np.float64)

_DEBUG_LIMIT_PER_CAM = int(os.environ.get("OBSERVATION_PIPELINE_DEBUG_LIMIT", "24"))
_MODE_FILE = "/tmp/observation_pipeline_mode"
_DEBUG_FILE = "/tmp/observation_pipeline_debug"
_RAY_BUFFER_MAX = 64
_RAY_BUFFER_MAX_AGE_S = 0.25


def _pipeline_debug_enabled() -> bool:
  if os.path.exists(_DEBUG_FILE):
    return True
  return os.environ.get("OBSERVATION_PIPELINE_DEBUG", "").strip().lower() in (
    "1", "true", "yes", "on",
  )


def _pipeline_mode() -> str:
  if os.path.exists(_MODE_FILE):
    try:
      return open(_MODE_FILE, encoding="utf-8").read().strip().lower() or "full"
    except OSError:
      pass
  return os.environ.get("OBSERVATION_PIPELINE_MODE", "full").strip().lower() or "full"


def _triangulation_enabled() -> bool:
  """Multi-view triangulation is opt-in (see module docstring)."""
  return os.environ.get("OBSERVATION_TRIANGULATION", "").strip().lower() in (
    "1", "true", "yes", "on",
  )


def sceneUsesObservationConditioning(scene_name: str) -> bool:
  if _pipeline_mode() == "off":
    return False
  return scene_name in OBSERVATION_CONDITIONING_SCENE_NAMES


def _euler_xyz_degrees_to_rmat(rotation) -> np.ndarray:
  """Match CameraPose / scipy Rotation.from_euler('XYZ', ..., degrees=True)."""
  rx, ry, rz = [np.deg2rad(float(a)) for a in rotation]
  cx, sx = np.cos(rx), np.sin(rx)
  cy, sy = np.cos(ry), np.sin(ry)
  cz, sz = np.cos(rz), np.sin(rz)
  # Extrinsic XYZ: R = Rz @ Ry @ Rx
  rx_m = np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]], dtype=np.float64)
  ry_m = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float64)
  rz_m = np.array([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
  return rz_m @ ry_m @ rx_m


def sceneMeshPoseMat(scene) -> np.ndarray:
  """4x4 mesh→world pose from scene mesh_translation/rotation/scale.

  Uses unit scale when mesh_scale is missing. Does not fall back to
  Scene.scale (map pixels-per-meter), which is not a GLB scale.
  Matches CameraPose._poseToPoseMat convention (R|t) @ diag(scale,1).
  """
  translation = getattr(scene, "mesh_translation", None) or [0.0, 0.0, 0.0]
  rotation = getattr(scene, "mesh_rotation", None) or [0.0, 0.0, 0.0]
  scale = _mesh_scale_xyz(getattr(scene, "mesh_scale", None))
  rmat = _euler_xyz_degrees_to_rmat(rotation)
  tvecs = np.asarray(translation, dtype=np.float64).reshape(3, 1)
  pose_mat = np.vstack((np.hstack((rmat, tvecs)), [0.0, 0.0, 0.0, 1.0]))
  return pose_mat @ np.diag([scale[0], scale[1], scale[2], 1.0])


def _mesh_scale_xyz(mesh_scale) -> list[float]:
  if mesh_scale is None:
    return [1.0, 1.0, 1.0]
  if isinstance(mesh_scale, (int, float)):
    # Explicit scalar mesh_scale only; never Scene.scale (map px/m).
    value = float(mesh_scale)
    if value <= 0.0:
      return [1.0, 1.0, 1.0]
    return [value, value, value]
  try:
    values = [float(mesh_scale[0]), float(mesh_scale[1]), float(mesh_scale[2])]
  except (TypeError, IndexError, ValueError):
    return [1.0, 1.0, 1.0]
  if any(v <= 0.0 for v in values):
    return [1.0, 1.0, 1.0]
  return values


class ObservationPipeline:
  """Per-scene cache of AmodalReasoner instances keyed by camera id."""

  def __init__(self, scene):
    self._ray_buffer: deque = deque(maxlen=_RAY_BUFFER_MAX)
    self.scene = scene
    self._reasoners: dict[str, object] = {}
    self._reasoner_keys: dict[str, tuple] = {}
    self._world_mesh = None
    self._world_mesh_key = None
    self._debug_counts: dict[str, int] = {}
    self._logged_mesh_once = False
    return

  def invalidate(self):
    self._reasoners.clear()
    self._reasoner_keys.clear()
    self._world_mesh = None
    self._world_mesh_key = None
    self._debug_counts.clear()
    self._logged_mesh_once = False
    self._ray_buffer.clear()
    return

  def _prune_ray_buffer(self, when: float) -> None:
    while self._ray_buffer and (
        when - float(self._ray_buffer[0].timestamp) > _RAY_BUFFER_MAX_AGE_S):
      self._ray_buffer.popleft()

  def _refine_with_triangulation(
    self,
    *,
    cam_id: str,
    category: str,
    when: float,
    origin: np.ndarray,
    ray: np.ndarray,
    mono_point: np.ndarray,
    mono_var: float,
    skip: bool,
  ) -> tuple[np.ndarray, float, bool]:
    """Try multi-view triangulation against recent other-camera rays.

    Returns (point, variance, used_triangulation).
    """
    from observation_conditioning.triangulation import (
      RayObservation,
      try_triangulate_pair,
    )

    self._prune_ray_buffer(when)
    obs = RayObservation(
      cam_id=str(cam_id),
      category=str(category or "unknown"),
      timestamp=float(when),
      origin=np.asarray(origin, dtype=np.float64).reshape(3).copy(),
      ray=np.asarray(ray, dtype=np.float64).reshape(3).copy(),
      mono_point=np.asarray(mono_point, dtype=np.float64).reshape(3).copy(),
      mono_var=float(mono_var),
    )

    best = None
    if not skip:
      for other in self._ray_buffer:
        result = try_triangulate_pair(obs, other)
        if result is None:
          continue
        if best is None or result.gap < best.gap:
          best = result

    self._ray_buffer.append(obs)

    if best is None:
      return mono_point, mono_var, False
    return best.point, best.variance, True


  def _raw_mesh_tensor(self):
    import open3d as o3d

    mesh = getattr(self.scene, "map_triangle_mesh", None)
    if mesh is None:
      return None
    if isinstance(mesh, o3d.t.geometry.TriangleMesh):
      return mesh
    if isinstance(mesh, o3d.geometry.TriangleMesh):
      return o3d.t.geometry.TriangleMesh.from_legacy(mesh)
    log.warn("ObservationPipeline: unsupported mesh type", type(mesh))
    return None

  def _mesh_pose_key(self, pose_mat: np.ndarray) -> tuple:
    return tuple(np.round(np.asarray(pose_mat, dtype=np.float64).reshape(-1), 6).tolist())

  def _world_mesh_tensor(self):
    """Clone map mesh and apply scene mesh pose into camera/world frame."""
    raw = self._raw_mesh_tensor()
    if raw is None:
      return None
    pose_mat = sceneMeshPoseMat(self.scene)
    key = (id(getattr(self.scene, "map_triangle_mesh", None)), self._mesh_pose_key(pose_mat))
    if self._world_mesh is not None and self._world_mesh_key == key:
      return self._world_mesh

    try:
      import open3d as o3d

      world = raw.clone()
      world.transform(o3d.core.Tensor(np.asarray(pose_mat, dtype=np.float64)))
    except Exception as exc:  # noqa: BLE001
      log.error("ObservationPipeline: failed to transform mesh to world", exc)
      return None

    self._world_mesh = world
    self._world_mesh_key = key
    if _pipeline_debug_enabled():
      log.info("ObservationPipeline: mesh→world pose applied",
               f"translation={getattr(self.scene, 'mesh_translation', None)}",
               f"rotation={getattr(self.scene, 'mesh_rotation', None)}",
               f"mesh_scale={_mesh_scale_xyz(getattr(self.scene, 'mesh_scale', None))}")
    return world

  def _log_mesh_frame_once(self, mesh, cam_origin):
    if self._logged_mesh_once or not _pipeline_debug_enabled():
      return
    self._logged_mesh_once = True
    try:
      aabb = mesh.get_axis_aligned_bounding_box()
      mn = aabb.min_bound.numpy().astype(float)
      mx = aabb.max_bound.numpy().astype(float)
      extents = mx - mn
      cam_origin = np.asarray(cam_origin, dtype=float)
      log.info(
        "ObservationPipeline:ZDBG mesh_aabb",
        f"min={mn.tolist()}",
        f"max={mx.tolist()}",
        f"extent={extents.tolist()}",
        f"mesh_translation={getattr(self.scene, 'mesh_translation', None)}",
        f"mesh_rotation={getattr(self.scene, 'mesh_rotation', None)}",
        f"mesh_scale={getattr(self.scene, 'mesh_scale', None)}",
        f"cam_origin={cam_origin.tolist()}",
        f"world_up={DEFAULT_WORLD_UP.tolist()}",
      )
      inside_xy = (mn[0] <= cam_origin[0] <= mx[0]) and (mn[1] <= cam_origin[1] <= mx[1])
      log.info(
        "ObservationPipeline:ZDBG mesh_cam_overlap",
        f"cam_inside_mesh_xy={inside_xy}",
        f"cam_z={float(cam_origin[2]):.3f}",
        f"mesh_z_range=[{mn[2]:.3f},{mx[2]:.3f}]",
        f"tallest_axis={int(np.argmax(extents))}(0=x,1=y,2=z)",
      )
    except Exception as exc:  # noqa: BLE001
      log.warn("ObservationPipeline:ZDBG mesh dump failed", exc)
    return

  def _camera_intrinsics_dict(self, camera) -> dict[str, float] | None:
    pose = getattr(camera, "pose", None)
    if pose is None or not hasattr(pose, "intrinsics"):
      return None
    k = np.asarray(pose.intrinsics.intrinsics, dtype=np.float64)
    if k.shape != (3, 3):
      return None
    resolution = getattr(pose, "resolution", None)
    if resolution is None:
      resolution = pose.intrinsics.getResolutionFromIntrinsics()
    width = float(resolution[0])
    height = float(resolution[1])
    return {
      "fx": float(k[0, 0]),
      "fy": float(k[1, 1]),
      "cx": float(k[0, 2]),
      "cy": float(k[1, 2]),
      "width": width,
      "height": height,
    }

  def _reasoner_for_camera(self, camera):
    from observation_conditioning import AmodalReasoner

    mesh = self._world_mesh_tensor()
    if mesh is None:
      return None
    intr = self._camera_intrinsics_dict(camera)
    if intr is None:
      return None
    pose_mat = np.asarray(camera.pose.pose_mat, dtype=np.float64)
    mesh_pose = sceneMeshPoseMat(self.scene)
    cam_id = camera.cameraID
    key = (
      round(intr["fx"], 4), round(intr["fy"], 4),
      round(intr["cx"], 4), round(intr["cy"], 4),
      int(intr["width"]), int(intr["height"]),
      tuple(np.round(pose_mat.reshape(-1), 5).tolist()),
      self._mesh_pose_key(mesh_pose),
      id(self.scene.map_triangle_mesh),
    )
    if self._reasoners.get(cam_id) is not None and self._reasoner_keys.get(cam_id) == key:
      return self._reasoners[cam_id]

    k_mat = np.array([
      [intr["fx"], 0.0, intr["cx"]],
      [0.0, intr["fy"], intr["cy"]],
      [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    try:
      reasoner = AmodalReasoner(
        mesh=mesh,
        rwc_z_up=DEFAULT_WORLD_UP.copy(),
        camera_intrinsics=k_mat,
        camera_extrinsics=pose_mat,
        width=int(intr["width"]),
        height=int(intr["height"]),
        num_layers=4,
      )
      if _pipeline_debug_enabled():
        reasoner.debug = True
    except Exception as exc:  # noqa: BLE001 — fall back to legacy path
      log.error("ObservationPipeline: failed to build AmodalReasoner for",
                cam_id, exc)
      return None

    self._reasoners[cam_id] = reasoner
    self._reasoner_keys[cam_id] = key
    log.info("ObservationPipeline: built AmodalReasoner for", cam_id,
             f"{int(intr['width'])}x{int(intr['height'])}",
             f"mode={_pipeline_mode()}")
    self._log_mesh_frame_once(mesh, pose_mat[:3, 3])
    return reasoner

  def _should_debug(self, cam_id: str) -> bool:
    if not _pipeline_debug_enabled():
      return False
    count = self._debug_counts.get(cam_id, 0)
    if count >= _DEBUG_LIMIT_PER_CAM:
      return False
    self._debug_counts[cam_id] = count + 1
    return True

  @staticmethod
  def _depth_map_t_hit(reasoner, u: float, v: float) -> float | None:
    """O(1) first-hit range from the camera DepthMap at pixel (u, v)."""
    dm = reasoner.depth_map
    if dm.t_hit_map is None:
      return None
    x = int(round(u))
    y = int(round(v))
    if x < 0 or y < 0 or x >= dm.width or y >= dm.height:
      return None
    t = dm.t_hit_map[y, x]
    if np.ndim(t) > 0:
      t = t[0]
    t = float(t)
    if not np.isfinite(t) or t <= 0.0:
      return None
    return t

  @staticmethod
  def _pixel_ray_world(intr: dict, pose_mat: np.ndarray, u: float, v: float):
    """Unit world ray from camera origin through pixel (u, v)."""
    fx = float(intr["fx"])
    fy = float(intr["fy"])
    cx = float(intr["cx"])
    cy = float(intr["cy"])
    ray_c = np.array([(u - cx) / fx, (v - cy) / fy, 1.0], dtype=np.float64)
    ray_c /= np.linalg.norm(ray_c) + 1e-12
    rot = np.asarray(pose_mat[:3, :3], dtype=np.float64)
    origin = np.asarray(pose_mat[:3, 3], dtype=np.float64)
    ray_w = rot @ ray_c
    ray_w /= np.linalg.norm(ray_w) + 1e-12
    return origin, ray_w

  def _project_bb_foot_to_mesh(self, reasoner, bb: dict, pose_mat: np.ndarray,
                               intr: dict) -> np.ndarray | None:
    """Project BB bottom-center onto the scene mesh via the precomputed depth map.

    Same geometric idea as legacy planar foot projection, but the hit is the
    GLB surface (stairs/landings) instead of z=0. Used when the object-library
    ``project_to_map`` flag is enabled (caller lifts to CoM afterward).
    """
    u = float(bb["x"]) + 0.5 * float(bb["width"])
    v = float(bb["y"]) + float(bb["height"])
    t_hit = self._depth_map_t_hit(reasoner, u, v)
    if t_hit is None:
      return None
    origin, ray_w = self._pixel_ray_world(intr, pose_mat, u, v)
    return origin + ray_w * t_hit

  @staticmethod
  def _object_half_height(mobj, default_height_m: float) -> float:
    """Half object height (m) for foot→CoM lift; prefer asset size_z."""
    size = getattr(mobj, "size", None)
    if size is not None and len(size) >= 3:
      try:
        hz = float(size[2])
        if np.isfinite(hz) and hz > 0.0:
          return 0.5 * hz
      except (TypeError, ValueError):
        pass
    return 0.5 * float(default_height_m)

  @staticmethod
  def _com_from_foot_hit(foot_xyz: np.ndarray, half_height_m: float,
                         world_up: np.ndarray | None = None) -> np.ndarray:
    """Lift a mesh foot contact point to geometric / mass center along world-up."""
    up = DEFAULT_WORLD_UP if world_up is None else np.asarray(world_up, dtype=np.float64)
    up = up / (np.linalg.norm(up) + 1e-12)
    return np.asarray(foot_xyz, dtype=np.float64) + up * float(half_height_m)

  def apply(self, objects: list, camera, when) -> list:
    """Overwrite world locations using frustum + amodal; on failure leave legacy."""
    from scene_common.geometry import Point
    from controller.moving_object import Chronoloc, Vector

    if not objects:
      return objects

    intr = self._camera_intrinsics_dict(camera)
    if intr is None:
      return objects

    detections = []
    usable = []
    for mobj in objects:
      bb = getattr(mobj, "boundingBoxPixels", None)
      if bb is None:
        continue
      detections.append({
        "bounding_box_px": {
          "x": float(bb.x),
          "y": float(bb.y),
          "width": float(bb.width),
          "height": float(bb.height),
        },
      })
      usable.append(mobj)

    if not detections:
      return objects

    cam_id = camera.cameraID
    mode = _pipeline_mode()
    do_dbg = self._should_debug(cam_id)
    want_mesh_project = any(getattr(o, "project_to_map", False) for o in usable)

    try:
      import frustum_gaussian as fg

      for i, mobj in enumerate(usable):
        detections[i]["axis_aware_sizing"] = bool(
          getattr(mobj, "axis_aware_sizing", True))
        # Prefer Asset3D size (object library) as frustum shape prior so
        # non-person classes (e.g. basketball) are not forced to PERSON_SHAPE_PRIOR.
        size = getattr(mobj, "size", None)
        if size is not None and len(size) >= 3:
          detections[i]["shape_prior"] = {
            "mu_x": float(size[0]),
            "mu_y": float(size[1]),
            "mu_z": float(size[2]),
            "sigma_x": 0.0,
            "sigma_y": 0.0,
            "sigma_z": 0.0,
          }
      cam_obs = fg.from_scenescape_detections(
        detections, intr, shape_prior=fg.PERSON_SHAPE_PRIOR)
      pose_mat = np.asarray(camera.pose.pose_mat, dtype=np.float32)
      world_obs = fg.transform_to_world_batch(cam_obs, pose_mat)

      # Amodal expects mu = camera origin in world, ray/depth along that ray.
      cam_origin = pose_mat[:3, 3].astype(np.float32)
      count = len(detections)
      gaus_rays = {
        "mu": np.tile(cam_origin, (count, 1)),
        "Sigma": world_obs["Sigma"],
        "ray": world_obs["ray"],
        "depth_est": world_obs["depth_est"],
        "depth_lo": world_obs["depth_lo"],
        "depth_hi": world_obs["depth_hi"],
        "depth_sigma": world_obs["depth_sigma"],
        "score": world_obs["score"],
        "edge_valid": world_obs["edge_valid"],
      }

      reasoner = None
      if mode != "frustum_only" or want_mesh_project:
        reasoner = self._reasoner_for_camera(camera)
        if reasoner is None and mode != "frustum_only":
          return objects

      if mode == "frustum_only" or reasoner is None:
        updated_depth = np.asarray(gaus_rays["depth_est"], dtype=np.float64).copy()
        updated_var = np.asarray(gaus_rays["depth_sigma"], dtype=np.float64) ** 2
      else:
        updated_depth, updated_var = reasoner.generate(gaus_rays)

      centroids = gaus_rays["mu"] + gaus_rays["ray"] * updated_depth[:, None]
      mesh_projected = [False] * count

      # Object-library "Project to map": foot on mesh, then lift to CoM so MQTT
      # translation stays the geometric center (UI places assets there unchanged).
      if want_mesh_project and reasoner is not None:
        default_h = float(fg.PERSON_SHAPE_PRIOR["mu_z"])
        for i, mobj in enumerate(usable):
          if not getattr(mobj, "project_to_map", False):
            continue
          foot = self._project_bb_foot_to_mesh(
            reasoner, detections[i]["bounding_box_px"], pose_mat, intr)
          if foot is None:
            continue
          half_h = self._object_half_height(mobj, default_h)
          centroids[i] = self._com_from_foot_hit(foot, half_h)
          mesh_projected[i] = True
          # Mesh contact is sharp; keep a small depth variance on the CoM.
          updated_var[i] = min(float(updated_var[i]), 0.05 ** 2)

      if do_dbg:
        mu_remap_err = float(np.max(np.abs(
          gaus_rays["mu"] - cam_origin[None, :])))
        legacy_z = None
        if usable and getattr(usable[0], "location", None):
          try:
            legacy_z = float(usable[0].location[0].point.z)
          except Exception:  # noqa: BLE001
            legacy_z = None
        for i in range(min(count, 3)):
          bb = detections[i]["bounding_box_px"]
          d_est = float(gaus_rays["depth_est"][i])
          d_upd = float(updated_depth[i])
          log.info(
            "ObservationPipeline:ZDBG",
            f"mode={mode}",
            f"cam={cam_id}",
            f"A_bb=({bb['x']:.1f},{bb['y']:.1f},{bb['width']:.1f},{bb['height']:.1f})",
            f"A_K=({intr['fx']:.2f},{intr['fy']:.2f},{intr['cx']:.2f},{intr['cy']:.2f})",
            f"A_res={int(intr['width'])}x{int(intr['height'])}",
            f"A_cam_origin={cam_origin.tolist()}",
            f"B_depth_est={d_est:.3f}",
            f"B_depth_lo={float(gaus_rays['depth_lo'][i]):.3f}",
            f"B_depth_hi={float(gaus_rays['depth_hi'][i]):.3f}",
            f"B_mu_cam_z={float(cam_obs['mu'][i, 2]):.3f}",
            f"B_score={float(gaus_rays['score'][i]):.3f}",
            f"B_edge_valid={int(gaus_rays['edge_valid'][i])}",
            f"C_world_mu={world_obs['mu'][i].tolist()}",
            f"C_ray={world_obs['ray'][i].tolist()}",
            f"D_mu_remap_err={mu_remap_err:.6f}",
            f"D_gaus_mu={gaus_rays['mu'][i].tolist()}",
            f"E_updated_depth={d_upd:.3f}",
            f"E_delta_depth={d_upd - d_est:.3f}",
            f"E_updated_var={float(updated_var[i]):.5f}",
            f"F_centroid={centroids[i].tolist()}",
            f"F_mesh_project={mesh_projected[i]}",
            f"F_legacy_z_before={legacy_z}",
            f"F_prior_half_height={0.5 * fg.PERSON_SHAPE_PRIOR['mu_z']:.3f}",
          )

      tri_count = 0
      use_tri = _triangulation_enabled()
      for i, mobj in enumerate(usable):
        used_tri = False
        if use_tri:
          category = str(getattr(mobj, "category", None) or "unknown")
          ray_i = np.asarray(gaus_rays["ray"][i], dtype=np.float64)
          mono_pt = np.asarray(centroids[i], dtype=np.float64)
          mono_var = float(updated_var[i])
          point, var, used_tri = self._refine_with_triangulation(
            cam_id=cam_id,
            category=category,
            when=float(when),
            origin=cam_origin.astype(np.float64),
            ray=ray_i,
            mono_point=mono_pt,
            mono_var=mono_var,
            skip=bool(mesh_projected[i]),
          )
          if used_tri:
            # Soft support: CoM cannot sit below half object height (ball on floor).
            half_h = self._object_half_height(
              mobj, float(fg.PERSON_SHAPE_PRIOR["mu_z"]))
            if point[2] < half_h:
              point = point.copy()
              point[2] = half_h
            tri_count += 1
            centroids[i] = point
            updated_var[i] = var
            if do_dbg:
              log.info(
                "ObservationPipeline:ZDBG",
                f"cam={cam_id}",
                f"G_triangulated=1",
                f"G_point={point.tolist()}",
                f"G_var={var:.5f}",
                f"G_mono={mono_pt.tolist()}",
              )

        world_pt = Point(centroids[i].tolist())
        mobj.orig_point = world_pt
        mobj.has_measured_z = True
        mobj.location = [Chronoloc(world_pt, when, mobj.boundingBox)]
        mobj.vectors = [Vector(camera, world_pt, when)]
        mobj.observation_depth_var = float(updated_var[i])
        mobj.observation_sigma = world_obs["Sigma"][i]
        mobj.observation_triangulated = bool(used_tri)

      log.debug("ObservationPipeline: conditioned", len(usable),
                "detections for", camera.cameraID, f"mode={mode}",
                f"mesh_project={sum(mesh_projected)}",
                f"triangulated={tri_count}")
    except Exception as exc:  # noqa: BLE001 — keep legacy projection
      log.error("ObservationPipeline: conditioning failed for",
                camera.cameraID, exc, "; using legacy projection")
    return objects
