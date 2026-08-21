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

# 'rack' lives in the SAME 'castellan' keystore as the 'castellan' alias, not
# a separate one. rack's load balancer signs/decrypts ESSR traffic as the
# 'castellan' AID directly (see rack.app.routing.Router.hab/create_load_balancer),
# which requires castellan's private key material to be present in rack's own
# Habery -- there's no OOBI/witness path for a load balancer AID to borrow
# another AID's signing key. So 'rack' and 'castellan' must share a keystore,
# same as nightingale's create_castellan_aids.sh does.
#
# We don't go through `castellan up` for this one -- it also registers a
# Mongo 'Server' doc (see ServerService.create_server), and creating a second
# Server doc for the 'rack' alias would silently become the "active server"
# returned by /oobi/server (ServerService.get_active_server picks the most
# recently registered one), displacing 'castellan'. Use raw `kli` instead,
# same as nightingale, which only touches the KERI keystore.
if ! kli aid --name castellan --alias rack >/dev/null 2>&1; then
  echo "Provisioning 'rack' AID (load balancer identity)..."
  kli incept --name castellan --alias rack --transferable --icount 1 --isith "1" --ncount 1 --nsith "1" --toad 0
  RACK_AID=$(kli aid --name castellan --alias rack)
  kli ends add --name castellan --alias rack --role controller --eid "${RACK_AID}"
  kli location add --name castellan --alias rack --url "tcp://castellan-rack:${CASTELLAN_RACK_PORT}" --eid "${RACK_AID}"
else
  echo "'rack' AID already exists; skipping."
fi

# rack hard-requires a TEL credential registry named 'rack' to exist under the
# 'rack' AID (see rack/core/scheming.py Routery.__init__). `kli vc registry
# incept` has no "already exists" guard, so gate it behind a marker on the
# persistent keri_data volume -- it only ever needs to run once.
REGISTRY_MARKER=/usr/local/var/keri/.castellan-rack-registry-provisioned
if [ ! -f "${REGISTRY_MARKER}" ]; then
  echo "Provisioning 'rack' TEL registry..."
  kli vc registry incept --name castellan --alias rack --registry-name rack
  touch "${REGISTRY_MARKER}"
else
  echo "'rack' TEL registry already provisioned; skipping."
fi

echo "Provisioning complete."