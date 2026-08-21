#!/bin/bash
set -euo pipefail

exec rack start \
  --name castellan-rack \
  --config-dir=/app/rack/docker/conf \
  --config-file=castellan-loadbalancer.json \
  --metrics-host 0.0.0.0 \
  --metrics-port "${CASTELLAN_RACK_METRICS_PORT}"