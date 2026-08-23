#!/bin/bash
set -euo pipefail

# Creates the KERI identifiers (AIDs) that castellan and castellan-rack need
# before they can start, then registers rack's AID as the OOBI-resolvable
# server -- see ServerService.get_active_server: rack, not castellan, is the
# externally-reachable identity, so `castellan up` runs against the rack
# alias once its TCP location scheme exists. Safe to re-run: each step is
# guarded by an existence check.

if [ ! -d /usr/local/var/keri/ks/castellan ]; then
  echo "Initializing 'castellan' keystore..."
  kli init --name castellan --nopasscode
fi

if ! kli aid --name castellan --alias castellan >/dev/null 2>&1; then
  echo "Provisioning 'castellan' AID (credential server identity)..."
  kli incept --name castellan --alias castellan --transferable --icount 1 --isith "1" --ncount 1 --nsith "1" --toad 0
else
  echo "'castellan' AID already exists; skipping."
fi

if ! kli aid --name castellan --alias rack >/dev/null 2>&1; then
  echo "Provisioning 'rack' AID (load balancer identity)..."
  kli incept --name castellan --alias rack --transferable --icount 1 --isith "1" --ncount 1 --nsith "1" --toad 0
  RACK_AID=$(kli aid --name castellan --alias rack)
  kli ends add --name castellan --alias rack --role controller --eid "${RACK_AID}"
  kli location add --name castellan --alias rack --url "tcp://${CASTELLAN_RACK_LOCATION_HOST:-castellan-rack}:${CASTELLAN_RACK_PORT}" --eid "${RACK_AID}"
else
  echo "'rack' AID already exists; skipping."
fi

echo "Registering 'rack' as the OOBI-resolvable server..."
up_args=(
  --name castellan
  --alias rack
  --dbhost "${MONGODB_HOST}"
  --dbname "${CASTELLAN_DB_NAME}"
)

if [ -n "${CASTELLAN_DB_USER:-}" ]; then
  up_args+=(--dbuser "${CASTELLAN_DB_USER}")
fi

if [ -n "${CASTELLAN_DB_PASS:-}" ]; then
  up_args+=(--dbpass "${CASTELLAN_DB_PASS}")
fi

castellan up "${up_args[@]}"

REGISTRY_MARKER=/usr/local/var/keri/.castellan-rack-registry-provisioned
if [ ! -f "${REGISTRY_MARKER}" ]; then
  echo "Provisioning 'rack' TEL registry..."
  kli vc registry incept --name castellan --alias rack --registry-name rack
  touch "${REGISTRY_MARKER}"
else
  echo "'rack' TEL registry already provisioned; skipping."
fi

echo "Provisioning complete."