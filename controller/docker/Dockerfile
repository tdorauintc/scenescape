# Copyright (C) 2021-2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials,
# and your use of them is governed by the express license under which they
# were provided to you ("License"). Unless the License provides otherwise,
# you may not use, modify, copy, publish, distribute, disclose or transmit
# this software or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express
# or implied warranties, other than those that are expressly stated in the License.

FROM ubuntu:22.04 AS scenescape-common-base

# We use root for runtime init. The command in ENTRYPOINT will drop to an unprivileged user.
# hadolint ignore=DL3002
USER root

ARG USER_ID
ARG CERTDOMAIN=scenescape.intel.com

ENV DEBIAN_FRONTEND=noninteractive

# TODO: remove dependencies not needed in this stage
RUN : \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        # Keep package list in alphabetical order
        g++ \
        libglib2.0-0 \
        libgl1-mesa-glx \
        libgtest-dev \
        make \
        patch \
        pybind11-dev \
        python-is-python3 \
        python3-pip \
        # TODO: investigate why removing this breaks the build. scipy is included in requirements-controller.txt
        python3-scipy \
        python3-venv \
    && apt-get purge -y python3-numpy \
    && rm -rf /var/lib/apt/lists/*

ENV ENV_DIR=/tmp/venv

# create virtual environment and install 3rd party python dependencies
COPY controller/docker/requirements-controller.txt /tmp
RUN : \
    && mkdir ${ENV_DIR} \
    && python3 -m venv --system-site-packages ${ENV_DIR} \
    && ${ENV_DIR}/bin/pip3 install --upgrade --no-cache-dir pip \
    && ${ENV_DIR}/bin/pip3 install --upgrade --no-cache-dir -r /tmp/requirements-controller.txt \
    && rm -rf /tmp/requirements-controller.txt

ENV PATH="${ENV_DIR}/bin:${PATH}"

# Install common dependencies
COPY ./scene_common tmp/scene_common
RUN cd tmp/scene_common \
    && pip install --no-cache-dir . \
    && make -C fast_geometry -j $(nproc) all install \
    && cd .. \
    && rm -rf scene_common

COPY ./utils/waitforbroker /tmp/utils/waitforbroker

FROM ubuntu:22.04 AS scenescape-controller-builder

USER root

ENV DEBIAN_FRONTEND=noninteractive

# TODO: copy common dependencies from scenescape-common-base stage instead of install
RUN : \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        cmake \
        g++ \
        libeigen3-dev \
        libgtest-dev \
        libopencv-dev \
        make \
        pybind11-dev \
        python3-pip \
        python3-scipy \
        python3-venv \
        python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

# Set up Python virtual  environment
ENV ENV_DIR=/tmp/venv
COPY --from=scenescape-common-base $ENV_DIR $ENV_DIR
COPY --from=scenescape-common-base /usr/local/lib/python3.10/dist-packages/fast_geometry ${ENV_DIR}/lib/python3.10/site-packages/fast_geometry
ENV PATH="${ENV_DIR}/bin:${PATH}"

# Build robot vision package
COPY ./controller/robot_vision /tmp/robot_vision
RUN export OpenCV_DIR="/usr/lib/x86_64-linux-gnu/cmake/opencv4" \
    && cd /tmp/robot_vision \
    && python3 setup.py bdist_wheel \
    && cd dist \
    && pip3 install --no-cache-dir ./*.whl

# Build main controller package
# TODO: simplify folder structure, so that one COPY is enough
COPY ./controller/src/controller /tmp/controller/src/controller
COPY ./controller/tools/analytics /tmp/controller/tools/analytics
COPY ./controller/setup.py /tmp/controller/setup.py
RUN cd /tmp/controller \
    && pip3 install --no-cache-dir .

# TODO: use slimmer image for runtime stage
FROM ubuntu:22.04 AS scenescape-controller-runtime

ENV WSUSER=scenescape
ENV SCENESCAPE_HOME=/home/$WSUSER/SceneScape
ENV BUILD_ENV_DIR=/tmp/venv
ENV ENV_DIR=/home/$WSUSER/venv

ENV DEBIAN_FRONTEND=noninteractive

USER root

RUN : \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libopencv-dev \
        netbase \
        pybind11-dev \
        python3-pip \
        python3-venv \
        python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

RUN : \
    && useradd -r -m -s /bin/bash $WSUSER \
    && usermod -a -G video,users $WSUSER \
    && eval WSHOME=~$WSUSER \
    && chmod a+rX "${WSHOME}"

# TODO: uncomment when issue with accessing the secrets is resolved
# USER $WSUSER

# setup up Python virtual environment
COPY --chown=$WSUSER:$WSUSER --from=scenescape-controller-builder $BUILD_ENV_DIR $ENV_DIR
ENV PATH="${ENV_DIR}/bin:${PATH}"

COPY --chown=$WSUSER:$WSUSER ./controller/schema/metadata.schema.json $SCENESCAPE_HOME/schema/metadata.schema.json
COPY --chown=$WSUSER:$WSUSER ./controller/tracker-config.json $SCENESCAPE_HOME/tracker-config.json
COPY --chown=$WSUSER:$WSUSER --from=scenescape-common-base /tmp/utils/waitforbroker $SCENESCAPE_HOME/utils/waitforbroker
COPY --chown=$WSUSER:$WSUSER ./controller/controller $SCENESCAPE_HOME/controller
COPY --chown=$WSUSER:$WSUSER ./controller/docker/controller-init /usr/local/bin/

ENTRYPOINT ["/usr/local/bin/controller-init"]
