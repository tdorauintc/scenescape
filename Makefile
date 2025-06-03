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
	@echo "Building image(s) in folder $@..."
	@$(MAKE) -C $@ http_proxy=$(http_proxy) https_proxy=$(https_proxy) no_proxy=$(no_proxy) $(EXTRA_BUILD_FLAGS)
	@echo "Image(s) in folder $@ built successfully."

# Parallel wrapper
.PHONY: build-images-parallel
build-images-parallel: build-common
	@echo "==> Running parallel builds of folders: $(FOLDERS)"
	@$(MAKE) -j$(JOBS) $(FOLDERS)
	@echo "DONE ==> Parallel builds of folders: $(FOLDERS)"

.PHONY: list-dependencies
list-dependencies:
	@echo "Listing dependencies for all microservices..."
	for dir in $(IMAGE_FOLDERS); do \
		$(MAKE) -C $$dir list-deps; \
	done
#TODO: generate a summary files with all dependencies
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
