#!/bin/bash
set -euo pipefail

exec castellan start \
  --name castellan \
  --alias castellan \
  --dbhost "${MONGODB_HOST}" \
  --dbname "${CASTELLAN_DB_NAME}" \
  --host 0.0.0.0 \
  --port "${CASTELLAN_PORT}"