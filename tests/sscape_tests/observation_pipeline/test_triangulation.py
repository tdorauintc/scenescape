# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for multi-view ray triangulation."""

import numpy as np

from observation_conditioning.triangulation import (
  RayObservation,
  triangulate_rays,
  try_triangulate_pair,
)


def test_triangulate_perpendicular_cameras():
  # Object at (1, 1, 0); cams on axes looking toward it.
  origin_a = np.array([0.0, 0.0, 0.0])
  ray_a = np.array([1.0, 1.0, 0.0])
  ray_a /= np.linalg.norm(ray_a)
  origin_b = np.array([2.0, 0.0, 0.0])
  ray_b = np.array([-1.0, 1.0, 0.0])
  ray_b /= np.linalg.norm(ray_b)

  result = triangulate_rays(origin_a, ray_a, origin_b, ray_b)
  assert result is not None
  point, gap, depth_a, depth_b = result
  assert gap < 1e-6
  np.testing.assert_allclose(point, [1.0, 1.0, 0.0], atol=1e-6)
  assert depth_a > 0.0 and depth_b > 0.0


def test_triangulate_rejects_parallel_rays():
  origin_a = np.array([0.0, 0.0, 0.0])
  origin_b = np.array([1.0, 0.0, 0.0])
  ray = np.array([0.0, 1.0, 0.0])
  assert triangulate_rays(origin_a, ray, origin_b, ray) is None


def test_try_triangulate_pair_same_category():
  true_pt = np.array([1.5, 2.0, 0.8])
  o_a = np.array([0.0, 0.0, 1.8])
  o_b = np.array([3.0, 0.0, 1.8])
  ray_a = true_pt - o_a
  ray_a /= np.linalg.norm(ray_a)
  ray_b = true_pt - o_b
  ray_b /= np.linalg.norm(ray_b)
  # Monocular points biased too close along each ray.
  mono_a = o_a + ray_a * 1.0
  mono_b = o_b + ray_b * 1.0

  a = RayObservation(
    cam_id="bball-cam1", category="basketball", timestamp=1.0,
    origin=o_a, ray=ray_a, mono_point=mono_a, mono_var=0.1)
  b = RayObservation(
    cam_id="bball-cam2", category="basketball", timestamp=1.05,
    origin=o_b, ray=ray_b, mono_point=mono_b, mono_var=0.1)

  result = try_triangulate_pair(a, b)
  assert result is not None
  np.testing.assert_allclose(result.point, true_pt, atol=1e-5)
  assert result.variance < 0.1


def test_try_triangulate_pair_rejects_mismatched_category():
  o = np.array([0.0, 0.0, 0.0])
  r = np.array([0.0, 1.0, 0.0])
  a = RayObservation(
    "c1", "basketball", 1.0, o, r, o + r, 0.1)
  b = RayObservation(
    "c2", "person", 1.0, o + [1, 0, 0], r, o + [1, 0, 0] + r, 0.1)
  assert try_triangulate_pair(a, b) is None
