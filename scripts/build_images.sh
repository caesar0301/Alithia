#!/usr/bin/env bash
#
# Build the Alithia Docker image (backend + frontend, single image).
#
# Usage:
#   ./scripts/build_images.sh              # build with default tag
#   ./scripts/build_images.sh --tag v0.3.0 # custom tag
#   ./scripts/build_images.sh --push       # build and push to registry
#
set -euo pipefail

REPO="${DOCKER_REPO:-registry.cn-hangzhou.aliyuncs.com/lacogito/alithia}"
TAG="${TAG:-latest}"
PUSH=false
PLATFORMS=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --tag)   TAG="$2"; shift 2 ;;
    --push)  PUSH=true; shift ;;
    --repo)  REPO="$2"; shift 2 ;;
    --platform) PLATFORMS="--platform $2"; shift 2 ;;
    *)       echo "Unknown option: $1"; exit 1 ;;
  esac
done

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "==> Building ${REPO}:${TAG}..."
docker build ${PLATFORMS} -t "${REPO}:${TAG}" -f Dockerfile .
echo "    Done."

if $PUSH; then
  echo "==> Pushing ${REPO}:${TAG}..."
  docker push "${REPO}:${TAG}"
  echo "    Push complete."
fi

echo "==> All done."
