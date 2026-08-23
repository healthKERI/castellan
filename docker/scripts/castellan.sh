#!/bin/bash
set -euo pipefail

args=(
  --name castellan
  --alias castellan
  --dbhost "${MONGODB_HOST}"
  --dbname "${CASTELLAN_DB_NAME}"
  --host 0.0.0.0
  --port "${CASTELLAN_PORT}"
)

if [ -n "${CASTELLAN_DB_USER:-}" ]; then
  args+=(--dbuser "${CASTELLAN_DB_USER}")
fi

if [ -n "${CASTELLAN_DB_PASS:-}" ]; then
  args+=(--dbpass "${CASTELLAN_DB_PASS}")
fi

exec castellan start "${args[@]}"