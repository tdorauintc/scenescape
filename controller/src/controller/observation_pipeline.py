# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Stairs-first observation pipeline: frustum Gaussian → amodal conditioning.

Converts 2D detections into mesh-conditioned world points for the existing
IntelLabs probabilistic tracker. Non-Stairs scenes keep the legacy path.
"""

from __future__ import annotations

import numpy as np
import open3d as o3d

import frustum_gaussian as fg
from observation_conditioning import AmodalReasoner
from scene_common import log
from scene_common.geometry import Point

from controller.moving_object import Chronoloc, MovingObject, Vector

# Hard-gate for Phase 1 verification (plan: Stairs-only).
OBSERVATION_CONDITIONING_SCENE_NAMES = frozenset({"Stairs"})

# Default world-up for SceneScape meshes (Z-up).
DEFAULT_WORLD_UP = np.array([0.0, 0.0, 1.0], dtype=np.float64)


def sceneUsesObservationConditioning(scene_name: str) -> bool:
  return scene_name in OBSERVATION_CONDITIONING_SCENE_NAMES


class ObservationPipeline:
  """Per-scene cache of AmodalReasoner instances keyed by camera id."""

  def __init__(self, scene):
    self.scene = scene
    self._reasoners: dict[str, AmodalReasoner] = {}
    self._reasoner_keys: dict[str, tuple] = {}
    return

  def invalidate(self):
    self._reasoners.clear()
    self._reasoner_keys.clear()
    return

  def _mesh_tensor(self):
    mesh = getattr(self.scene, "map_triangle_mesh", None)
    if mesh is None:
      return None
    if isinstance(mesh, o3d.t.geometry.TriangleMesh):
      return mesh
    if isinstance(mesh, o3d.geometry.TriangleMesh):
      return o3d.t.geometry.TriangleMesh.from_legacy(mesh)
    log.warn("ObservationPipeline: unsupported mesh type", type(mesh))
    return None

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

  def _reasoner_for_camera(self, camera) -> AmodalReasoner | None:
    mesh = self._mesh_tensor()
    if mesh is None:
      return None
    intr = self._camera_intrinsics_dict(camera)
    if intr is None:
      return None
    pose_mat = np.asarray(camera.pose.pose_mat, dtype=np.float64)
    cam_id = camera.cameraID
    key = (
      round(intr["fx"], 4), round(intr["fy"], 4),
      round(intr["cx"], 4), round(intr["cy"], 4),
      int(intr["width"]), int(intr["height"]),
      tuple(np.round(pose_mat.reshape(-1), 5).tolist()),
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
    except Exception as exc:  # noqa: BLE001 — fall back to legacy path
      log.error("ObservationPipeline: failed to build AmodalReasoner for",
                cam_id, exc)
      return None

    self._reasoners[cam_id] = reasoner
    self._reasoner_keys[cam_id] = key
    log.info("ObservationPipeline: built AmodalReasoner for", cam_id,
             f"{int(intr['width'])}x{int(intr['height'])}")
    return reasoner

  def apply(self, objects: list[MovingObject], camera, when) -> list[MovingObject]:
    """Overwrite world locations using frustum + amodal; on failure leave legacy."""
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

    try:
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

      reasoner = self._reasoner_for_camera(camera)
      if reasoner is None:
        return objects

      updated_depth, updated_var = reasoner.generate(gaus_rays)
      centroids = gaus_rays["mu"] + gaus_rays["ray"] * updated_depth[:, None]

      for i, mobj in enumerate(usable):
        world_pt = Point(centroids[i].tolist())
        mobj.orig_point = world_pt
        mobj.has_measured_z = True
        mobj.location = [Chronoloc(world_pt, when, mobj.boundingBox)]
        mobj.vectors = [Vector(camera, world_pt, when)]
        mobj.observation_depth_var = float(updated_var[i])
        mobj.observation_sigma = world_obs["Sigma"][i]

      log.debug("ObservationPipeline: conditioned", len(usable),
                "detections for", camera.cameraID)
    except Exception as exc:  # noqa: BLE001 — keep legacy projection
      log.error("ObservationPipeline: conditioning failed for",
                camera.cameraID, exc, "; using legacy projection")
    return objects
