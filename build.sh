#!/usr/bin/env bash

docker builder prune --all --force
docker build -t local-camoufox:latest -t local-camoufox:$(date "+%Y%m%d").1 . --push
