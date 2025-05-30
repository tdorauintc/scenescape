# Copyright (C) 2021-2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials,
# and your use of them is governed by the express license under which they
# were provided to you ("License"). Unless the License provides otherwise,
# you may not use, modify, copy, publish, distribute, disclose or transmit
# this software or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express
# or implied warranties, other than those that are expressly stated in the License.

'''
sscape URL Configuration
'''

from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings
from sscape import views
from sscape.calculate_intrinsics_view import CalculateCameraIntrinsics
from sscape.model_directory_view import ModelDirectory
from sscape.views import SingletonSensorDeleteView
from sscape.views import SingletonSensorUpdateView
from sscape.views import SingletonSensorDetailView
from sscape.views import SingletonSensorCreateView
from sscape.views import SingletonSensorListView
from sscape.views import CamDeleteView
from sscape.views import CamUpdateView
from sscape.views import CamDetailView
from sscape.views import CamCreateView
from sscape.views import CamListView
from sscape.views import SceneDeleteView
from sscape.views import SceneUpdateView
from sscape.views import SceneDetailView
from sscape.views import SceneCreateView
from sscape.views import SceneListView
from sscape.views import AssetDeleteView
from sscape.views import AssetUpdateView
from sscape.views import AssetCreateView
from sscape.views import AssetListView
from sscape.views import ChildDeleteView
from sscape.views import ChildUpdateView
from sscape.views import ChildCreateView
from sscape.views import ModelListView

# Imports for REST API
from django.urls import re_path
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
  path('admin/', admin.site.urls),
  path('', views.index, name='index'),
  path('<uuid:scene_id>/', views.sceneDetail, name='sceneDetail'),
  path('<uuid:scene_id>/roi', views.saveROI, name='save-roi'),
  path('scene/list/', SceneListView.as_view(), name='scene_list'),
  path('scene/create/', SceneCreateView.as_view(), name='scene_create'),
  path('scene/detail/<uuid:pk>/', SceneDetailView.as_view(), name='scene_detail'),
  path('scene/update/<uuid:pk>/', SceneUpdateView.as_view(), name='scene_update'),
  path('scene/delete/<uuid:pk>/', SceneDeleteView.as_view(), name='scene_delete'),
  path('cam/list/', CamListView.as_view(), name='cam_list'),
  path('cam/create/', CamCreateView.as_view(), name='cam_create'),
  path('cam/detail/<int:pk>/', CamDetailView.as_view(), name='cam_detail'),
  path('cam/update/<int:pk>/', CamUpdateView.as_view(), name='cam_update'),
  path('cam/delete/<int:pk>/', CamDeleteView.as_view(), name='cam_delete'),
  path('cam/calibrate/<int:sensor_id>', views.cameraCalibrate, name='cam_calibrate'),
  path('singleton_sensor/list/', SingletonSensorListView.as_view(), name='singleton_sensor_list'),
  path('singleton_sensor/create/', SingletonSensorCreateView.as_view(), name='singleton_sensor_create'),
  path('singleton_sensor/detail/<int:pk>/', SingletonSensorDetailView.as_view(), name='singleton_sensor_detail'),
  path('singleton_sensor/update/<int:pk>/', SingletonSensorUpdateView.as_view(), name='singleton_sensor_update'),
  path('singleton_sensor/delete/<int:pk>/', SingletonSensorDeleteView.as_view(), name='singleton_sensor_delete'),
  path('singleton_sensor/calibrate/<int:sensor_id>', views.genericCalibrate, name='singleton_sensor_calibrate'),
  path('asset/list/', AssetListView.as_view(), name='asset_list'),
  path('asset/create/', AssetCreateView.as_view(), name='asset_create'),
  path('asset/update/<int:pk>/', AssetUpdateView.as_view(), name='asset_update'),
  path('asset/delete/<int:pk>/', AssetDeleteView.as_view(), name='asset_delete'),
  path('child/create/', ChildCreateView.as_view(), name='child_create'),
  path('child/update/<int:pk>/', ChildUpdateView.as_view(), name='child_update'),
  path('child/delete/<int:pk>/', ChildDeleteView.as_view(), name='child_delete'),
  path('sign_in/', views.sign_in, name="sign_in"),
  path('sign_out/', views.sign_out, name="sign_out"),
  path('account_locked/', views.account_locked, name="account_locked"),
  re_path(r'^%s(?P<path>.*)$' % settings.MEDIA_URL[1:],
          views.protected_media,
          {'media_root': settings.MEDIA_ROOT}),
  re_path(r'^%s(?P<path>.*)$' % settings.DOCS_URL[1:],
          views.protected_media,
          {'media_root': settings.DOCS_ROOT}),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
  import debug_toolbar
  urlpatterns = [
    path('__debug__/', include(debug_toolbar.urls)),
  ] + urlpatterns

if settings.KUBERNETES_SERVICE_HOST:
  urlpatterns += [
    path('model/list/', ModelListView.as_view(), name='model_list'),
    re_path(r'^%s(?P<path>.*)$' % settings.MODEL_URL[1:],
            views.protected_media,
            {'media_root': settings.MODEL_ROOT},
            name="model_resources"),
  ]

# REST API

urlpatterns += [
  re_path(r'api/v1/(scenes)$', views.ListThings.as_view()),
  re_path(r'api/v1/(scene)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(scene)/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})$', views.ManageThing.as_view()),
  re_path(r'api/v1/(cameras)$', views.ListThings.as_view()),
  re_path(r'api/v1/(camera)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(camera)/([^/]+)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(sensors)$', views.ListThings.as_view()),
  re_path(r'api/v1/(sensor)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(sensor)/([^/]+)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(regions)$', views.ListThings.as_view()),
  re_path(r'api/v1/(region)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(region)/([^/]+)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(tripwires)$', views.ListThings.as_view()),
  re_path(r'api/v1/(tripwire)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(tripwire)/([^/]+)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(users)$', views.ListThings.as_view()),
  re_path(r'api/v1/(user)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(user)/([^/]+)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(frame)$', views.CameraManager.as_view()),
  re_path(r'api/v1/(video)$', views.CameraManager.as_view()),
  re_path(r'api/v1/(assets)$', views.ListThings.as_view()),
  re_path(r'api/v1/(asset)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(asset)/([^/]+)$', views.ManageThing.as_view()),
  re_path(r'api/v1/scenes/(child)$', views.ListThings.as_view()),
  re_path(r'api/v1/(child)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(child)/([^/]+)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(calibrationmarkers)$', views.ListThings.as_view()),
  re_path(r'api/v1/(calibrationmarker)$', views.ManageThing.as_view()),
  re_path(r'api/v1/(calibrationmarker)/([^/]+)$', views.ManageThing.as_view())
]

urlpatterns += [
  path('api/', include('rest_framework.urls')),
  path('api/v1/auth', views.CustomAuthToken.as_view(), name='api_token_auth'),
  path('api/v1/database-ready', views.DatabaseReady.as_view()),
  path('api/v1/calculateintrinsics', CalculateCameraIntrinsics.as_view()),
  path('api/v1/aclcheck', views.ACLCheck.as_view())
]

if settings.KUBERNETES_SERVICE_HOST:
  urlpatterns += [
    path('api/v1/model-directory/', ModelDirectory.as_view(), name='model-directory'),
  ]
