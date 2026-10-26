# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from django.db import migrations, models


class Migration(migrations.Migration):

  dependencies = [
    ("manager", "0005_default_asset3d_objects"),
  ]

  operations = [
    migrations.AddField(
      model_name="asset3d",
      name="axis_aware_sizing",
      field=models.BooleanField(
        choices=[(True, "Yes"), (False, "No")],
        default=True,
        help_text=(
          "When enabled, frustum depth uses BB width for object width and BB "
          "height for object height (better for upright people). When disabled, "
          "uses an orientation-averaged size (better when yaw is unknown)."
        ),
        null=True,
        verbose_name="Axis-aware frustum sizing",
      ),
    ),
  ]
