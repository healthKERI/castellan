#!/bin/bash
set -euo pipefail

# `rack start` only replays load balancer routes already persisted as TEL
# credentials (see rack.app.routing.Router.setup, which reads rt.routes.values()
# and never creates any) -- the route itself has to be issued once via
# `rack route create`. `rack route create` has no "already exists" guard, and
# issuing it twice would spin up two TcpSrvProc listeners on the same port, so
# gate it behind a marker on the persistent keri_data volume.
ROUTE_MARKER=/usr/local/var/keri/.castellan-loadbalancer-route-provisioned
if [ ! -f "${ROUTE_MARKER}" ]; then
  echo "Provisioning castellan load balancer route..."
  CASTELLAN_AID=$(kli aid --name castellan --alias castellan)
  ROUTE_CONFIG=$(printf '{"aid":"%s","tcpsrv":{"host":"0.0.0.0","port":%s},"http_hosts":[{"host":"castellan","port":%s}]}' \
    "${CASTELLAN_AID}" "${CASTELLAN_RACK_PORT}" "${CASTELLAN_PORT}")
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