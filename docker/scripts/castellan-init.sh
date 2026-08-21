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

echo "Provisioning 'rack' AID (load balancer identity)..."
# 'rack' lives in its own keystore (castellan-rack), not the 'castellan'
# keystore. `rack start` opens its keystore by --name directly (see
# rack.app.racking.setup), so if it shared the 'castellan' keystore, the
# castellan-rack container and the castellan container would both hold that
# LMDB env open at once from separate processes/PID namespaces -- which LMDB
# does not support and reliably fails with
# `mdb_txn_begin: Resource temporarily unavailable`.
castellan up \
  --name castellan-rack \
  --alias rack \
  --dbhost "${MONGODB_HOST}" \
  --dbname "${CASTELLAN_DB_NAME}" \
  --ipaddress castellan-rack \
  --port "${CASTELLAN_RACK_PORT}"

# rack hard-requires a TEL credential registry named 'rack' to exist under the
# 'rack' AID (see rack/core/scheming.py Routery.__init__). `kli vc registry
# incept` has no "already exists" guard, so gate it behind a marker on the
# persistent keri_data volume -- it only ever needs to run once.
REGISTRY_MARKER=/usr/local/var/keri/.castellan-rack-registry-provisioned
if [ ! -f "${REGISTRY_MARKER}" ]; then
  echo "Provisioning 'rack' TEL registry..."
  kli vc registry incept --name castellan-rack --alias rack --registry-name rack
  touch "${REGISTRY_MARKER}"
else
  echo "'rack' TEL registry already provisioned; skipping."
fi

echo "Provisioning complete."