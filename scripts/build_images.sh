#!/usr/bin/env bash
#
# Build Docker images for the Alithia platform.
#
# Usage:
#   ./scripts/build_images.sh              # build all images with default tags
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

echo "==> Building images with tag: ${TAG}"
echo "    Repository prefix: ${REPO}"
echo ""

# --- Full image (backend + frontend in one) ---
echo "==> Building ${REPO}:${TAG} (full image with backend + frontend)..."
docker build ${PLATFORMS} -t "${REPO}:${TAG}" -f Dockerfile .
echo "    Done."

# --- Backend-only image ---
echo "==> Building ${REPO}-backend:${TAG}..."
docker build ${PLATFORMS} -t "${REPO}-backend:${TAG}" -f Dockerfile.backend .
echo "    Done."

# --- Dashboard frontend image ---
echo "==> Building ${REPO}-dashboard:${TAG}..."
docker build ${PLATFORMS} -t "${REPO}-dashboard:${TAG}" -f Dockerfile.dashboard .
echo "    Done."

echo ""
echo "==> Built images:"
echo "    ${REPO}:${TAG}"
echo "    ${REPO}-backend:${TAG}"
echo "    ${REPO}-dashboard:${TAG}"

if $PUSH; then
  echo ""
  echo "==> Pushing images..."
  docker push "${REPO}:${TAG}"
  docker push "${REPO}-backend:${TAG}"
  docker push "${REPO}-dashboard:${TAG}"
  echo "    Push complete."
fi

echo ""
echo "==> All done."
