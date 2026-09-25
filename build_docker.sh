#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${1:-notarymindai:latest}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but not installed or not on PATH." >&2
  exit 1
fi

echo "Building Docker image: ${IMAGE_NAME}"
docker build \
  --file "${ROOT_DIR}/docker/Dockerfile" \
  --tag "${IMAGE_NAME}" \
  "${ROOT_DIR}"

echo "Built: ${IMAGE_NAME}"
