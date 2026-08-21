#!/bin/bash
set -euo pipefail

exec castellan oobi start \
  --dbhost "${MONGODB_HOST}" \
  --dbname "${CASTELLAN_DB_NAME}" \
  --host 0.0.0.0 \
  --port "${CASTELLAN_OOBI_PORT}"