COMPOSE_FILE = docker.compose.yaml
IMAGE_NAME ?= bms-rev1
IMAGE_TAG ?= latest

.PHONY: build push deploy

build:
	IMAGE_NAME=$(IMAGE_NAME) IMAGE_TAG=$(IMAGE_TAG) docker compose -f $(COMPOSE_FILE) build

push:
	IMAGE_NAME=$(IMAGE_NAME) IMAGE_TAG=$(IMAGE_TAG) docker compose -f $(COMPOSE_FILE) push

deploy:
	IMAGE_NAME=$(IMAGE_NAME) IMAGE_TAG=$(IMAGE_TAG) docker compose -f $(COMPOSE_FILE) up -d

