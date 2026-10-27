# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Multi-view ray triangulation for camera observations.

Frustum Gaussian is monocular (BB + shape prior → range). Amodal conditioning
is per-camera mesh truncation. When two (or more) calibrated cameras observe
the same object, intersecting their world rays recovers metric depth without
a size prior or MDE — camera-only; other modalities already carry range.

Cross-observation conditioning for the observation pipeline toolbox. Wired
behind ``OBSERVATION_TRIANGULATION=1`` (off by default; revisit when
association and baseline geometry are strong enough).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Reject nearly parallel cameras / grazing baselines.
_MIN_RAY_CROSS_NORM = 1e-4
# Midpoint of the common perpendicular must lie in front of both cameras.
_MIN_DEPTH_M = 0.05
# Require a usable stereo baseline between camera centers (meters).
# Below ~0.2 m at room scale, depth is poorly conditioned; still allow a
# modest floor so demos with slightly underestimated MapAnything baselines
# can exercise the path.
_MIN_BASELINE_M = 0.12

# Association: max distance between skew-line midpoints (meters).
DEFAULT_MAX_PAIR_GAP_M = 0.75
# Association: max |t1-t2| (seconds) between camera frames.
DEFAULT_MAX_DT_S = 0.20



@dataclass(frozen=True)
class RayObservation:
  """One camera's world-space bearing for an object."""

  cam_id: str
  category: str
  timestamp: float
  origin: np.ndarray  # (3,) camera center in world
  ray: np.ndarray  # (3,) unit direction world
  mono_point: np.ndarray  # (3,) monocular frustum/amodal centroid
  mono_var: float  # along-ray depth variance (m^2)


@dataclass(frozen=True)
class TriangulationResult:
  point: np.ndarray  # (3,) world
  gap: float  # length of common perpendicular (m)
  depth_a: float
  depth_b: float
  variance: float  # isotropic xyz variance proxy for tracker R


def triangulate_rays(
  origin_a: np.ndarray,
  ray_a: np.ndarray,
  origin_b: np.ndarray,
  ray_b: np.ndarray,
) -> tuple[np.ndarray, float, float, float] | None:
  """Closest-point midpoint of two skew lines in R^3.

  Returns (point, gap, depth_a, depth_b) or None if rays are parallel / behind.
  """
  o1 = np.asarray(origin_a, dtype=np.float64).reshape(3)
  d1 = np.asarray(ray_a, dtype=np.float64).reshape(3)
  o2 = np.asarray(origin_b, dtype=np.float64).reshape(3)
  d2 = np.asarray(ray_b, dtype=np.float64).reshape(3)
  n1 = np.linalg.norm(d1)
  n2 = np.linalg.norm(d2)
  if n1 < 1e-12 or n2 < 1e-12:
    return None
  d1 = d1 / n1
  d2 = d2 / n2

  cross = np.cross(d1, d2)
  cross_norm = float(np.linalg.norm(cross))
  if cross_norm < _MIN_RAY_CROSS_NORM:
    return None

  # Solve for depths along each ray minimizing ||(o1+s d1) - (o2+t d2)||.
  # [ d1·d1, -d1·d2 ] [s] = [ d1·(o2-o1) ]
  # [ d2·d1, -d2·d2 ] [t]   [ d2·(o2-o1) ]
  w0 = o1 - o2
  a = float(np.dot(d1, d1))
  b = float(np.dot(d1, d2))
  c = float(np.dot(d2, d2))
  d = float(np.dot(d1, w0))
  e = float(np.dot(d2, w0))
  denom = a * c - b * b
  if abs(denom) < 1e-12:
    return None
  s = (b * e - c * d) / denom
  t = (a * e - b * d) / denom
  if s < _MIN_DEPTH_M or t < _MIN_DEPTH_M:
    return None

  p1 = o1 + s * d1
  p2 = o2 + t * d2
  gap = float(np.linalg.norm(p1 - p2))
  point = 0.5 * (p1 + p2)
  return point, gap, float(s), float(t)


def triangulation_variance(gap: float, depth_a: float, depth_b: float,
                           mono_var_a: float, mono_var_b: float) -> float:
  """Conservative isotropic variance for the triangulated point."""
  # Geometric: residual gap + depth-dependent baseline uncertainty.
  mean_depth = 0.5 * (depth_a + depth_b)
  geo = max(gap, 0.02) ** 2 + (0.02 * mean_depth) ** 2
  # Cap by the better monocular variance (stereo should not be worse).
  mono = min(float(mono_var_a), float(mono_var_b))
  return float(min(max(geo, 1e-4), mono))


def try_triangulate_pair(
  a: RayObservation,
  b: RayObservation,
  *,
  max_gap_m: float = DEFAULT_MAX_PAIR_GAP_M,
  max_dt_s: float = DEFAULT_MAX_DT_S,
) -> TriangulationResult | None:
  """Associate and triangulate two observations if they are compatible."""
  if a.cam_id == b.cam_id:
    return None
  if a.category != b.category:
    return None
  if abs(float(a.timestamp) - float(b.timestamp)) > max_dt_s:
    return None
  baseline = float(np.linalg.norm(
    np.asarray(a.origin, dtype=np.float64) - np.asarray(b.origin, dtype=np.float64)))
  if baseline < _MIN_BASELINE_M:
    return None

  tri = triangulate_rays(a.origin, a.ray, b.origin, b.ray)
  if tri is None:
    return None
  point, gap, depth_a, depth_b = tri
  if gap > max_gap_m:
    return None

  # Prefer stereo when it is not wildly inconsistent with both mono means.
  mono_err_a = float(np.linalg.norm(point - a.mono_point))
  mono_err_b = float(np.linalg.norm(point - b.mono_point))
  # Allow large mono bias (the bug we are fixing) but reject absurd outliers.
  if mono_err_a > 5.0 and mono_err_b > 5.0:
    return None

  var = triangulation_variance(gap, depth_a, depth_b, a.mono_var, b.mono_var)
  return TriangulationResult(
    point=point, gap=gap, depth_a=depth_a, depth_b=depth_b, variance=var)
