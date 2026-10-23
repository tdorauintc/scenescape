# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for Stairs-only observation conditioning gate."""

from controller.observation_pipeline import (
  OBSERVATION_CONDITIONING_SCENE_NAMES,
  sceneUsesObservationConditioning,
)


def test_stairs_uses_observation_conditioning():
  assert sceneUsesObservationConditioning("Stairs") is True


def test_other_scenes_use_legacy_path():
  assert sceneUsesObservationConditioning("Retail") is False
  assert sceneUsesObservationConditioning("Queuing") is False
  assert sceneUsesObservationConditioning("") is False


def test_gate_set_is_stairs_only():
  assert OBSERVATION_CONDITIONING_SCENE_NAMES == frozenset({"Stairs"})
