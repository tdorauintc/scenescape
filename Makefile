# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

COMMON_FOLDER := scene_common
IMAGE_FOLDERS := docker controller autocalibration manager percebro
EXTRA_BUILD_FLAGS :=
TARGET_BRANCH ?= $(if $(CHANGE_TARGET),$(CHANGE_TARGET),$(BRANCH_NAME))
SHELL := /bin/bash
# Number of parallel jobs (defaults to CPU count)
JOBS ?= $(shell nproc)
FOLDERS ?= $(IMAGE_FOLDERS)
BUILD_DIR ?= $(PWD)/build

ifeq ($(or $(findstring DAILY,$(BUILD_TYPE)),$(findstring TAG,$(BUILD_TYPE))),true)
	EXTRA_BUILD_FLAGS := rebuild
endif
ifeq ($(or $(TARGET_BRANCH)),rc beta-rc)
	EXTRA_BUILD_FLAGS := rebuild
endif

default: build

.PHONY: build
build: check-tag build-certificates build-images-parallel

.PHONY: check-tag
check-tag:
ifeq ($(BUILD_TYPE),TAG)
	@echo "Checking if tag matches version.txt..."
	@if grep --quiet $(BRANCH_NAME) version.txt; then \
		echo "Perfect - Tag and Version is matching"; \
	else \
		echo "There is some mismatch between Tag and Version"; \
		exit 1; \
	fi
endif

.PHONY: build-certificates
build-certificates:
	@make -C certificates CERTPASS=$$(openssl rand -base64 12)

# Build common base image
.PHONY: build-common
build-common:
	@$(MAKE) -C $(COMMON_FOLDER) http_proxy=$(http_proxy) $(EXTRA_BUILD_FLAGS)
	@echo "DONE"

.PHONY: $(IMAGE_FOLDERS)
$(IMAGE_FOLDERS):
	@echo "====> Building folder $@..."
	@$(MAKE) -C $@ http_proxy=$(http_proxy) https_proxy=$(https_proxy) no_proxy=$(no_proxy) $(EXTRA_BUILD_FLAGS)
	@echo "DONE ====> Building folder $@"

# Parallel wrapper handles parallel builds of folders specified in FOLDERS variable
.PHONY: build-images-parallel
build-images-parallel: build-common
	@echo "==> Running parallel builds of folders: $(FOLDERS)"
# Use a trap to catch errors and print logs if any error occurs in parallel build
	@set -e; trap 'grep --color=auto -i -r --include="*.log" "^error" . || true' EXIT; \
	$(MAKE) -j$(JOBS) $(FOLDERS)
	@echo "DONE ==> Parallel builds of folders: $(FOLDERS)"

.PHONY: demo
demo:
	@$(MAKE) -C docker ../docker-compose.yml
	docker compose up -d

.PHONY: list-dependencies
list-dependencies:
	@echo "Listing dependencies for all microservices..."
	@set -e; \
	for dir in $(IMAGE_FOLDERS); do \
		$(MAKE) -C $$dir list-dependencies; \
	done
	@-find . -type f -name '*-apt-deps.txt' -exec cat {} + | sort | uniq > $(BUILD_DIR)/scenescape-all-apt-deps.txt
	@-find . -type f -name '*-pip-deps.txt' -exec cat {} + | sort | uniq > $(BUILD_DIR)/scenescape-all-pip-deps.txt
	@echo "The following dependency lists have been generated:"
	@find $(BUILD_DIR) -name '*-deps.txt' -print
	@echo "DONE"

.PHONY: clean
clean:
	@echo "Cleaning up all microservices..."
	for dir in $(IMAGE_FOLDERS); do \
		$(MAKE) -C $$dir clean; \
	done
	@echo "Cleaning common folder..."
	@$(MAKE) -C $(COMMON_FOLDER) clean
	@echo "Cleaning certificates..."
	@make -C certificates clean
	@echo "DONE"

.PHONY: rebuild
rebuild: clean build
