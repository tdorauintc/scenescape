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

# -------------- Common Base Stage --------------
FROM ubuntu:22.04 AS scenescape-common-base

# We use root for runtime init. The command in ENTRYPOINT will drop to an unprivileged user.
# hadolint ignore=DL3002
USER root
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN : \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        # Keep package list in alphabetical order
        g++ \
        make \
        python3-pip \
        # needed by fast_geometry
        python3-scipy \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

ENV ENV_DIR=/tmp/venv

# create and set up Python virtual environment
RUN : \
    && mkdir ${ENV_DIR} \
    && python3 -m venv ${ENV_DIR} \
    && ${ENV_DIR}/bin/pip3 install --upgrade --no-cache-dir pip \
    && ${ENV_DIR}/bin/pip3 install --no-cache-dir wheel \
    && ${ENV_DIR}/bin/pip install --no-cache-dir wheel

ENV PATH="${ENV_DIR}/bin:${PATH}"

# install common dependencies
COPY ./scene_common tmp/scene_common
RUN : \
    && cd tmp/scene_common \
    && pip install --no-cache-dir pybind11 \
    && pip install --no-cache-dir . \
    && make -C fast_geometry -j $(nproc) all install \
    && cd .. \
    && rm -rf scene_common

COPY ./utils/waitforbroker /tmp/utils/waitforbroker

# -------------- Controller Builder Stage --------------
FROM ubuntu:22.04 AS scenescape-controller-builder

USER root
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# TODO: copy common dependencies from previous stages instead of install
RUN : \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        cmake \
        libeigen3-dev \
        libgtest-dev \
        libopencv-dev \
        make \
        pybind11-dev \
        python3-pip \
        python3-scipy \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Set up Python virtual environment
ENV ENV_DIR=/tmp/venv
COPY --from=scenescape-common-base $ENV_DIR $ENV_DIR
COPY --from=scenescape-common-base /usr/local/lib/python3.10/dist-packages/fast_geometry ${ENV_DIR}/lib/python3.10/site-packages/fast_geometry
ENV PATH="${ENV_DIR}/bin:${PATH}"

# Install 3rd party python dependencies
COPY controller/requirements.txt /tmp
RUN : \
    && pip3 install --upgrade --no-cache-dir -r /tmp/requirements.txt \
    && rm -rf /tmp/requirements.txt

# Build robot vision package
COPY ./controller/src/robot_vision /tmp/robot_vision
RUN export OpenCV_DIR="/usr/lib/x86_64-linux-gnu/cmake/opencv4" \
    && cd /tmp/robot_vision \
    && python3 setup.py bdist_wheel \
    && cd dist \
    && pip3 install --no-cache-dir ./*.whl \
    && cd \
    && rm -rf /tmp/robot_vision

# Build main controller package
COPY ./controller/src/controller /tmp/controller
RUN cd /tmp/controller \
    && python3 setup.py bdist_wheel \
    && cd dist \
    && pip3 install --no-cache-dir ./*.whl \
    && cd \
    && rm -rf /tmp/controller

# TODO: use slimmer image for runtime stage
# -------------- Controller Runtime Stage --------------
FROM ubuntu:22.04 AS scenescape-controller-runtime

ARG USER_ID
ARG CERTDOMAIN=scenescape.intel.com

ENV WSUSER=scenescape
ENV SCENESCAPE_HOME=/home/$WSUSER/SceneScape
ENV BUILD_ENV_DIR=/tmp/venv
ENV ENV_DIR=/home/$WSUSER/venv
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

USER root

# TODO: copy common dependencies from previous stages instead of install
RUN : \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libopencv-dev \
        libpython3.10 \
        netbase \
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

COPY --chown=$WSUSER:$WSUSER ./controller/config/schema/metadata.schema.json $SCENESCAPE_HOME/schema/metadata.schema.json
COPY --chown=$WSUSER:$WSUSER ./controller/config/tracker-config.json $SCENESCAPE_HOME/tracker-config.json
COPY --chown=$WSUSER:$WSUSER --from=scenescape-common-base /tmp/utils/waitforbroker $SCENESCAPE_HOME/utils/waitforbroker
COPY --chown=$WSUSER:$WSUSER ./controller/src/controller-cmd $SCENESCAPE_HOME/controller-cmd
COPY --chown=$WSUSER:$WSUSER ./controller/src/controller-init /usr/local/bin/

ENTRYPOINT ["/usr/local/bin/controller-init"]
