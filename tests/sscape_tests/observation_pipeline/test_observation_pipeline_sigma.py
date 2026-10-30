# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the conditioned covariance handed to the tracker as R."""

import numpy as np

from controller.observation_pipeline import ObservationPipeline


def _frustum_sigma(ray, depth_sigma, lateral_sigma):
  """Ray-elongated Σ built like frustum_gaussian (ray is an eigenvector)."""
  ray = np.asarray(ray, dtype=np.float64)
  ray = ray / np.linalg.norm(ray)
  helper = np.array([0.0, 0.0, 1.0]) if abs(ray[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
  e_h = np.cross(ray, helper)
  e_h /= np.linalg.norm(e_h)
  e_v = np.cross(ray, e_h)
  return (lateral_sigma ** 2 * (np.outer(e_h, e_h) + np.outer(e_v, e_v))
          + depth_sigma ** 2 * np.outer(ray, ray)), ray


def test_conditioned_sigma_replaces_along_ray_variance_only():
  sigma, ray = _frustum_sigma([1.0, 2.0, -0.5], depth_sigma=2.0, lateral_sigma=0.1)

  conditioned = ObservationPipeline._conditioned_sigma(
    sigma, ray, depth_var=0.09, triangulated=False)

  assert np.isclose(ray @ conditioned @ ray, 0.09)
  lateral = np.cross(ray, [0.0, 0.0, 1.0])
  lateral /= np.linalg.norm(lateral)
  assert np.isclose(lateral @ conditioned @ lateral, 0.01)
  assert np.allclose(conditioned, conditioned.T)


def test_conditioned_sigma_unchanged_when_depth_variance_unchanged():
  sigma, ray = _frustum_sigma([0.0, 1.0, 0.0], depth_sigma=1.5, lateral_sigma=0.2)

  conditioned = ObservationPipeline._conditioned_sigma(
    sigma, ray, depth_var=1.5 ** 2, triangulated=False)

  assert np.allclose(conditioned, sigma)


def test_conditioned_sigma_is_isotropic_for_triangulated_points():
  sigma, ray = _frustum_sigma([1.0, 0.0, 0.0], depth_sigma=3.0, lateral_sigma=0.2)

  conditioned = ObservationPipeline._conditioned_sigma(
    sigma, ray, depth_var=0.04, triangulated=True)

  assert np.allclose(conditioned, np.eye(3) * 0.04)


def test_conditioned_sigma_floors_depth_variance_to_stay_positive_definite():
  sigma, ray = _frustum_sigma([1.0, 1.0, 0.0], depth_sigma=1.0, lateral_sigma=0.1)

  conditioned = ObservationPipeline._conditioned_sigma(
    sigma, ray, depth_var=0.0, triangulated=False)

  assert np.all(np.linalg.eigvalsh(conditioned) > 0.0)


def test_conditioned_sigma_stays_positive_definite_for_float32_far_depth():
  sigma, ray = _frustum_sigma([0.3, 1.0, -0.2], depth_sigma=30.0, lateral_sigma=0.05)

  conditioned = ObservationPipeline._conditioned_sigma(
    sigma.astype(np.float32), ray.astype(np.float32), depth_var=1e-4, triangulated=False)

  assert np.all(np.linalg.eigvalsh(conditioned) > 0.0)
  assert np.isclose(ray @ conditioned @ ray, 1e-4, rtol=1e-3)
