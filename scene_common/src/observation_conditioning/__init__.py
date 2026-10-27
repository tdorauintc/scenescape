# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Vendored from scenescape-v2-architecture/algorithms/amodalreasoner.
# See NOTICE in this package for provenance requirements.

"""Observation conditioning (amodal / scene-projection) for frustum Gaussians.

``AmodalReasoner`` depends on open3d, which is available in the controller
runtime image. Imports are lazy so scene_common-base can install the package
without open3d.
"""

__all__ = [
  "AmodalReasoner",
  "DepthMap",
  "RayObservation",
  "TriangulationResult",
  "triangulate_rays",
  "try_triangulate_pair",
]


def __getattr__(name):
  if name == "AmodalReasoner":
    from .amodal_reasoner import AmodalReasoner
    return AmodalReasoner
  if name == "DepthMap":
    from .intersection_map import DepthMap
    return DepthMap
  if name in (
      "RayObservation", "TriangulationResult",
      "triangulate_rays", "try_triangulate_pair"):
    from . import triangulation as _tri
    return getattr(_tri, name)
  raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
