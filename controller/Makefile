# Copyright (C) 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials,
# and your use of them is governed by the express license under which they
# were provided to you ("License"). Unless the License provides otherwise,
# you may not use, modify, copy, publish, distribute, disclose or transmit
# this software or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express
# or implied warranties, other than those that are expressly stated in the License.

IMAGE=scenescape-controller
VERSION:=$(shell cat ../version.txt)
BUILD_DIR=build

PHONY: build-image rebuild list-deps

default: build-image

build-image: Dockerfile
	env BUILDKIT_PROGRESS=plain \
	  docker build $(REBUILDFLAGS) \
	    --build-arg http_proxy=$(http_proxy) \
	    --build-arg https_proxy=$(https_proxy) \
	    --build-arg no_proxy=$(no_proxy) \
	    --build-arg CERTDOMAIN=$(CERTDOMAIN) \
	    --build-arg USER_ID=$$UID \
	    --rm -t $(IMAGE):$(VERSION) .. -f ./Dockerfile \
	&& docker tag $(IMAGE):$(VERSION) $(IMAGE):latest

rebuild:
	make REBUILDFLAGS="--no-cache"

list-deps: build-image
	mkdir -p ${BUILD_DIR} && cd ${BUILD_DIR}
	docker run --rm --entrypoint pip $(IMAGE):$(VERSION) freeze --all > pip-deps.txt
	docker run --rm ubuntu:22.04 dpkg -l | awk '{ print $2, $3, $4 }' > ubuntu-packages.txt
	docker run --rm $(IMAGE):$(VERSION) dpkg -l | awk '{ print $2, $3, $4 }' > controller-packages.txt
	grep -Fxv -f ubuntu-packages.txt controller-packages.txt > apt-deps.txt
	rm -rf ubuntu-packages.txt controller-packages.txt

clean:
	rm -rf ${BUILD_DIR}
	docker rmi $(IMAGE):$(VERSION) $(IMAGE):latest || true
