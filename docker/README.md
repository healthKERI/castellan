# Castellan Docker Setup

`docker compose up --build` (from the repo root) starts four containers:

| Service          | Image                     | Port(s)           | Purpose |
|-------------------|---------------------------|--------------------|---------|
| `mongodb`         | `mongo:8.0`               | 27017              | Backing store for castellan's KEL/TEL, accounts, and credential state. |
| `castellan-init`  | `docker/Dockerfile`       | —                  | One-shot: creates the `castellan` and `rack` KERI identifiers and rack's TEL registry (idempotent), then exits. |
| `castellan`       | `docker/Dockerfile.combined` | 5925, 5923, 5885 | Runs `castellan start` and `rack start` as two supervisord-managed processes sharing one keystore. |
| `castellan-oobi`  | `docker/Dockerfile`       | 5927               | The OOBI resolution service (`castellan oobi start`) — stateless, reads directly from MongoDB. |

## Why castellan and rack share a container and a keystore

`rack`'s load balancer signs and decrypts ESSR traffic *as* the `castellan` AID directly
(see `rack.app.routing.Router.hab` / `create_load_balancer` in the `rack` package) — there's
no OOBI or witness path for a load balancer to borrow another AID's signing key, so `castellan`'s
private key material has to be present in `rack`'s own Habery. That means `castellan` and `rack`
must live in the same KERI keystore, matching nightingale's `create_castellan_aids.sh`, which
incepts both under one `kli init --name castellan` keystore.

Running `castellan` and `rack` as separate long-running containers against that shared keystore
was tried and reliably failed: once `castellan` had been running for a bit, `rack start` would
fail every time with `mdb_txn_begin: Resource temporarily unavailable` (its startup sequence
opens ~90 LMDB sub-databases, and `castellan`'s escrow-processing loop holds the environment's
single writer lock often enough that the burst can't get through). Starting both processes
together in one container via `supervisord` — the same way nightingale runs them — avoids this;
`docker/Dockerfile.combined` installs both `castellan` and the vendored `rack` wheel, and
`docker/conf/supervisord.conf` manages the two processes.

`castellan-init` stays a separate one-shot container: `castellan start`/`rack start` require
their KERI identifiers and TEL registry to already exist, so `castellan-init` provisions those
once via `depends_on: condition: service_completed_successfully` before the combined `castellan`
container starts. It uses the plain `docker/Dockerfile` (`castellan` only) since it never touches
`rack`.

## Provisioning flow

- `castellan-init.sh` runs `castellan up` for the `castellan` alias, then (if not already
  present) raw `kli incept`/`ends add`/`location add` for the `rack` alias in the same keystore,
  then `kli vc registry incept` for rack's TEL registry (rack hard-requires a registry named
  `rack` to exist — see `rack/core/scheming.py`'s `Routery.__init__`).
- `castellan-rack.sh` provisions the load-balancer route itself on first boot: `rack start` only
  ever replays routes already persisted as TEL credentials (`rack.app.routing.Router.setup`
  reads `rt.routes.values()` and never creates any), so `castellan-rack.sh` runs
  `rack route create --type load_balancer` once, forwarding traffic to `castellan`'s own HTTP
  port over the docker network, before `exec rack start`. Both steps are gated behind markers on
  the persistent `keri_data` volume since neither `kli incept`/`ends add`/`location add` nor
  `rack route create` has an "already exists" guard.

## Config

`docker/conf/keri/cf/castellan-loadbalancer.json` is rack's resolver config — it tells rack
which MongoDB database to consult to route inbound requests. It's mounted into `castellan`
(not baked into the image) so it can be edited without a rebuild — read-write, not read-only:
rack's `Configer` opens it in `r+b` mode even just to read it, and on a read-only mount `hio`'s
fallback-to-`~/.keri/cf` path has a bug where a second open of that fallback file never actually
attaches a file handle, crashing `rack start`.

## Ports

- `5923` — rack's inbound ESSR (encrypted) traffic port.
- `5925` — castellan's HTTP API.
- `5927` — castellan's OOBI service.
- `5885` — rack's Prometheus metrics endpoint.