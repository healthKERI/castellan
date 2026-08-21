#!/bin/bash
set -euo pipefail

# Creates the KERI identifiers (AIDs) that castellan and castellan-rack need
# before they can start. `castellan up` is idempotent -- it only creates the
# hab if one doesn't already exist in the keystore -- so this is safe to run
# on every container start/restart.

echo "Provisioning 'castellan' AID (credential server identity)..."
castellan up \
  --name castellan \
  --alias castellan \
  --dbhost "${MONGODB_HOST}" \
  --dbname "${CASTELLAN_DB_NAME}" \
  --ipaddress castellan \
  --port "${CASTELLAN_PORT}"

if ! kli aid --name castellan --alias rack >/dev/null 2>&1; then
  echo "Provisioning 'rack' AID (load balancer identity)..."
  kli incept --name castellan --alias rack --transferable --icount 1 --isith "1" --ncount 1 --nsith "1" --toad 0
  RACK_AID=$(kli aid --name castellan --alias rack)
  kli ends add --name castellan --alias rack --role controller --eid "${RACK_AID}"
  kli location add --name castellan --alias rack --url "tcp://castellan-rack:${CASTELLAN_RACK_PORT}" --eid "${RACK_AID}"
else
  echo "'rack' AID already exists; skipping."
fi


REGISTRY_MARKER=/usr/local/var/keri/.castellan-rack-registry-provisioned
if [ ! -f "${REGISTRY_MARKER}" ]; then
  echo "Provisioning 'rack' TEL registry..."
  kli vc registry incept --name castellan --alias rack --registry-name rack
  touch "${REGISTRY_MARKER}"
else
  echo "'rack' TEL registry already provisioned; skipping."
fi

echo "Provisioning complete."