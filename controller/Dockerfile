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

ENV DEBIAN_FRONTEND=noninteractive

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
    && apt-get purge -y python3-numpy \
    && rm -rf /var/lib/apt/lists/*

ENV ENV_DIR=/tmp/venv

# create virtual environment and install 3rd party python dependencies
COPY controller/requirements.txt /tmp
RUN : \
    && mkdir ${ENV_DIR} \
    && python3 -m venv --system-site-packages ${ENV_DIR} \
    && ${ENV_DIR}/bin/pip3 install --upgrade --no-cache-dir pip \
    && ${ENV_DIR}/bin/pip3 install --upgrade --no-cache-dir -r /tmp/requirements.txt \
    && rm -rf /tmp/requirements.txt

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
        netbase \
        pybind11-dev \
        python3-pip \
        python3-scipy \
        python3-venv \
        python-is-python3 \
        # TODO: remove sudo when switching to non-root user is implemented
        sudo \
    && rm -rf /var/lib/apt/lists/*

ENV WSUSER=scenescape
ENV SCENESCAPE_HOME=/home/$WSUSER/SceneScape
# ENV BUILD_ENV_DIR=/tmp/venv
# ENV ENV_DIR=/home/$WSUSER/venv

RUN : \
    && useradd -r -m -s /bin/bash $WSUSER \
    && usermod -a -G video,users $WSUSER \
    && eval WSHOME=~$WSUSER \
    && chmod a+rX "${WSHOME}"

# Set up Python virtual  environment
ENV ENV_DIR=/tmp/venv
# TODO: use --chown=user:group when switching to non-root user is implemented
COPY --from=scenescape-common-base $ENV_DIR $ENV_DIR
COPY --from=scenescape-common-base /usr/local/lib/python3.10/dist-packages/fast_geometry ${ENV_DIR}/lib/python3.10/site-packages/fast_geometry
ENV PATH="${ENV_DIR}/bin:${PATH}"

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
COPY ./controller/src/controller $SCENESCAPE_HOME
RUN eval WSHOME=~$WSUSER \
    && chown -R "$WSUSER" "$SCENESCAPE_HOME" \
    && pip3 install --no-cache-dir "$SCENESCAPE_HOME/"

# TODO: use slimmer image for runtime stage
# FROM ubuntu:22.04 AS scenescape-controller-runtime

ARG USER_ID
ARG CERTDOMAIN=scenescape.intel.com

# TODO: use non-root user for runtime as soon as possible
# USER $WSUSER
# WORKDIR $SCENESCAPE_HOME

COPY --from=scenescape-common-base /tmp/utils/waitforbroker $SCENESCAPE_HOME/utils/waitforbroker
COPY ./controller/config/schema/metadata.schema.json $SCENESCAPE_HOME/schema/metadata.schema.json
COPY ./controller/config/tracker-config.json $SCENESCAPE_HOME/tracker-config.json
COPY ./controller/src/controller-app.py $SCENESCAPE_HOME/controller-app.py

# TODO: make separate run-time stage and copy only the required binaries there
COPY ./controller/src/controller-init /usr/local/bin/

ENTRYPOINT ["/usr/local/bin/controller-init"]
