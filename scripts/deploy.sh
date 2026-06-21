#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vpn_bot}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
GHCR_IMAGE="${GHCR_IMAGE:-}"
DOCKERHUB_IMAGE="${DOCKERHUB_IMAGE:-}"

IMAGE=""
if [[ -n "${GHCR_IMAGE}" ]]; then
  IMAGE="${GHCR_IMAGE}:${IMAGE_TAG}"
elif [[ -n "${DOCKERHUB_IMAGE}" ]]; then
  IMAGE="${DOCKERHUB_IMAGE}:${IMAGE_TAG}"
else
  echo "Either GHCR_IMAGE or DOCKERHUB_IMAGE must be set"
  exit 1
fi

mkdir -p "${APP_DIR}"
cd "${APP_DIR}"

if [[ ! -f ".env" ]]; then
  echo ".env not found in ${APP_DIR}"
  exit 1
fi

export VPN_BOT_IMAGE="${IMAGE}"

docker compose -f "${COMPOSE_FILE}" pull
docker compose -f "${COMPOSE_FILE}" up -d
docker image prune -f
