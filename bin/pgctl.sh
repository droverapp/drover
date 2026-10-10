#!/usr/bin/env bash
# Lightweight Postgres lifecycle manager for local development.
# Replaces Docker Compose for this project's single-container need.
set -euo pipefail

CONTAINER_NAME="drover-postgres"
DB_NAME="drover"
DB_USER="drover"
DB_PASS="drover"
DB_PORT="${DB_PORT:-5432}"

cmd="${1:-status}"

status() {
  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    local state
    state=$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || echo "false")
    echo "Container ${CONTAINER_NAME}: ${state}"
  else
    echo "Container ${CONTAINER_NAME}: not created yet"
  fi
}

start() {
  if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Already running."
    return 0
  fi

  # Recreate if it exists but is stopped
  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker start "$CONTAINER_NAME"
  else
    docker run -d \
      --name "$CONTAINER_NAME" \
      -e POSTGRES_DB="$DB_NAME" \
      -e POSTGRES_USER="$DB_USER" \
      -e POSTGRES_PASSWORD="$DB_PASS" \
      -p "$DB_PORT":5432 \
      postgres:16-alpine
  fi

  # Wait for Postgres to be ready
  echo -n "Waiting for Postgres... "
  for i in $(seq 1 30); do
    if docker exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
      echo "ready."
      return 0
    fi
    echo -n "."
    sleep 1
  done
  echo "timed out."
  echo "Hint: check 'docker logs $CONTAINER_NAME'"
  return 1
}

stop() {
  if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker stop "$CONTAINER_NAME"
    echo "Stopped."
  else
    echo "Not running."
  fi
}

reset() {
  stop 2>/dev/null || true
  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker rm "$CONTAINER_NAME"
  fi
  start
  echo "Postgres reset complete."
}

case "$cmd" in
  start)  start ;;
  stop)   stop ;;
  restart) stop; start ;;
  reset)  reset ;;
  status) status ;;
  *)
    echo "Usage: $0 {start|stop|restart|reset|status}"
    exit 1
    ;;
esac