#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vpn_bot}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

mkdir -p "${APP_DIR}"
cd "${APP_DIR}"

if [[ ! -f ".env" ]]; then
  echo ".env not found in ${APP_DIR}"
  exit 1
fi

docker compose -f "${COMPOSE_FILE}" up -d --build
docker image prune -f
