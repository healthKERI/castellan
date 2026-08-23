#!/bin/bash
set -euo pipefail

ROUTE_MARKER=/usr/local/var/keri/.castellan-loadbalancer-route-provisioned
if [ ! -f "${ROUTE_MARKER}" ]; then
  echo "Provisioning castellan load balancer route..."
  CASTELLAN_AID=$(kli aid --name castellan --alias castellan)
  ROUTE_CONFIG=$(printf '{"aid":"%s","tcpsrv":{"host":"0.0.0.0","port":%s},"http_hosts":[{"host":"%s","port":%s}]}' \
    "${CASTELLAN_AID}" "${CASTELLAN_RACK_PORT}" "${CASTELLAN_HTTP_HOST:-castellan}" "${CASTELLAN_PORT}")
  rack route create --name castellan --alias rack --type load_balancer --config "${ROUTE_CONFIG}"
  touch "${ROUTE_MARKER}"
else
  echo "castellan load balancer route already provisioned; skipping."
fi

exec rack start \
  --name castellan \
  --config-dir=/app/rack/docker/conf \
  --config-file=castellan-loadbalancer.json \
  --metrics-host 0.0.0.0 \
  --metrics-port "${CASTELLAN_RACK_METRICS_PORT}"