# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Smoke tests for vendored frustum_gaussian package."""

import numpy as np
import pytest

import frustum_gaussian as fg


def test_project_frustum_batch_person_box():
  boxes = np.array([[300.0, 100.0, 600.0, 700.0]], dtype=np.float32)
  priors = np.tile(
    [fg.PERSON_SHAPE_PRIOR["mu_x"], fg.PERSON_SHAPE_PRIOR["mu_y"],
     fg.PERSON_SHAPE_PRIOR["mu_z"], fg.PERSON_SHAPE_PRIOR["sigma_x"],
     fg.PERSON_SHAPE_PRIOR["sigma_y"], fg.PERSON_SHAPE_PRIOR["sigma_z"]],
    (1, 1)).astype(np.float32)
  intrinsics = np.array([943.69, 943.69, 640.0, 360.0], dtype=np.float32)
  img_size = np.array([1280.0, 720.0], dtype=np.float32)

  result = fg.project_frustum_batch(
    {"boxes": boxes, "priors": priors}, intrinsics, img_size)

  assert result["mu"].shape == (1, 3)
  assert result["Sigma"].shape == (1, 3, 3)
  assert result["depth_est"][0] > 0
  assert 0.0 <= result["score"][0] <= 1.0


def test_from_scenescape_detections_xywh_dict():
  detections = [{
    "bounding_box_px": {"x": 300, "y": 100, "width": 300, "height": 600},
  }]
  intrinsics = {
    "fx": 943.69, "fy": 943.69, "cx": 640.0, "cy": 360.0,
    "width": 1280.0, "height": 720.0,
  }
  result = fg.from_scenescape_detections(detections, intrinsics)
  assert result["mu"].shape == (1, 3)
  assert np.isfinite(result["mu"]).all()


def test_transform_to_world_batch_translation():
  boxes = np.array([[300.0, 100.0, 600.0, 700.0]], dtype=np.float32)
  priors = np.array([[0.55, 0.55, 1.7, 0.1, 0.1, 0.15]], dtype=np.float32)
  intrinsics = np.array([943.69, 943.69, 640.0, 360.0], dtype=np.float32)
  img_size = np.array([1280.0, 720.0], dtype=np.float32)
  cam = fg.project_frustum_batch(
    {"boxes": boxes, "priors": priors}, intrinsics, img_size)

  pose = np.eye(4, dtype=np.float32)
  pose[2, 3] = 5.0
  world = fg.transform_to_world_batch(cam, pose)
  np.testing.assert_allclose(world["mu"][0, 2], cam["mu"][0, 2] + 5.0, rtol=1e-5)


def test_empty_detections():
  result = fg.from_scenescape_detections([], {
    "fx": 1, "fy": 1, "cx": 0, "cy": 0, "width": 100, "height": 100,
  })
  assert result["mu"].shape == (0, 3)


def test_axis_aware_vs_orientation_averaged_depth():
  """Upright person BB: axis-aware depth is farther than orientation-averaged."""
  detections = [{
    "bounding_box_px": {"x": 843, "y": 81, "width": 251, "height": 503},
  }]
  intrinsics = {
    "fx": 943.69, "fy": 943.69, "cx": 640.0, "cy": 360.0,
    "width": 1280.0, "height": 720.0,
  }
  d_aa = float(fg.from_scenescape_detections(
    detections, intrinsics, axis_aware=True)["depth_est"][0])
  d_avg = float(fg.from_scenescape_detections(
    detections, intrinsics, axis_aware=False)["depth_est"][0])
  assert d_aa > d_avg
  assert abs(d_aa - 2.920) < 0.05
  assert abs(d_avg - 2.604) < 0.05
