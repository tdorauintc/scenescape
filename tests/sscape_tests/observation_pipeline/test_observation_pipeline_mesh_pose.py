# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for scene mesh→world pose used by ObservationPipeline."""

import numpy as np

from controller.observation_pipeline import _mesh_scale_xyz, sceneMeshPoseMat


class _FakeScene:
  def __init__(self, translation=None, rotation=None, mesh_scale=None, scale=None):
    self.mesh_translation = translation
    self.mesh_rotation = rotation
    self.mesh_scale = mesh_scale
    self.scale = scale


def test_mesh_scale_defaults_to_unit_when_missing():
  assert _mesh_scale_xyz(None) == [1.0, 1.0, 1.0]


def test_mesh_scale_accepts_xyz_triple():
  assert _mesh_scale_xyz([2.0, 3.0, 4.0]) == [2.0, 3.0, 4.0]


def test_scene_mesh_pose_applies_rotation_and_translation_unit_scale():
  # Stairs-like pose: 90° about X then translate by half-extents.
  scene = _FakeScene(
    translation=[3.5289487838745117, 4.484969615936279, 1.9587233066558838],
    rotation=[90.0, 0.0, 0.0],
    mesh_scale=None,
    scale=85.61930847167969,  # map px/m — must not be used
  )
  pose = sceneMeshPoseMat(scene)
  assert pose.shape == (4, 4)

  half = np.array([3.5289487838745117, 1.9587233066558838, 4.484969615936279])
  raw_corners = np.array([
    [x, y, z, 1.0]
    for x in (-half[0], half[0])
    for y in (-half[1], half[1])
    for z in (-half[2], half[2])
  ])
  world_corners = (pose @ raw_corners.T).T[:, :3]
  wmin, wmax = world_corners.min(axis=0), world_corners.max(axis=0)
  np.testing.assert_allclose(wmin, [0.0, 0.0, 0.0], atol=1e-5)
  np.testing.assert_allclose(wmax, [7.05789733, 8.96993923, 3.91744661], atol=1e-5)

  # Camera that was outside the raw GLB AABB sits inside the world mesh XY.
  cam = np.array([1.3124726404216402, 8.291039766593512, 2.240595194905057])
  assert wmin[0] <= cam[0] <= wmax[0]
  assert wmin[1] <= cam[1] <= wmax[1]


def test_scene_mesh_pose_ignores_map_scale_attribute():
  scene = _FakeScene(
    translation=[0.0, 0.0, 0.0],
    rotation=[0.0, 0.0, 0.0],
    mesh_scale=None,
    scale=85.0,
  )
  pose = sceneMeshPoseMat(scene)
  np.testing.assert_allclose(pose, np.eye(4), atol=1e-9)
