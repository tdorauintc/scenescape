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

IMAGE:=scenescape-controller
VERSION:=$(shell cat ../version.txt)
BUILD_DIR:=./build

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
	@mkdir -p $(BUILD_DIR)
	@docker run --rm --entrypoint pip $(IMAGE):$(VERSION) freeze --all > $(BUILD_DIR)/pip-deps.txt
	@echo "Python dependencies listed in $(BUILD_DIR)/pip-deps.txt"
	@docker run --rm ubuntu:22.04 dpkg -l | awk '{ print $$2, $$3, $$4 }' > $(BUILD_DIR)/ubuntu-packages.txt
	@docker run --rm --entrypoint dpkg $(IMAGE):$(VERSION) -l | awk '{ print $$2, $$3, $$4 }' > $(BUILD_DIR)/controller-packages.txt
	@grep -Fxv -f $(BUILD_DIR)/ubuntu-packages.txt $(BUILD_DIR)/controller-packages.txt > $(BUILD_DIR)/apt-deps.txt
	@rm -rf $(BUILD_DIR)/ubuntu-packages.txt $(BUILD_DIR)/controller-packages.txt
	@echo "OS dependencies listed in $(BUILD_DIR)/apt-deps.txt"

clean:
	rm -rf $(BUILD_DIR)
	docker rmi $(IMAGE):$(VERSION) $(IMAGE):latest || true
