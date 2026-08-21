# Castellan Docker Setup

`docker compose up --build` (from the repo root) starts five containers:

| Service          | Image              | Port(s)     | Purpose |
|-------------------|--------------------|-------------|---------|
| `mongodb`         | `mongo:8.0`        | 27017       | Backing store for castellan's KEL/TEL, accounts, and credential state. |
| `castellan-init`  | `docker/Dockerfile`| —           | One-shot: creates the `castellan` and `rack` KERI identifiers (idempotent), then exits. |
| `castellan`       | `docker/Dockerfile`| 5925        | The credential server (`castellan start`) — the Falcon HTTP API used by the plugin. |
| `castellan-oobi`  | `docker/Dockerfile`| 5927        | The OOBI resolution service (`castellan oobi start`) — stateless, reads directly from MongoDB. |
| `castellan-rack`  | `docker/Dockerfile.rack` | 5923, 5885 | The `rack` load balancer (`rack start`) that fronts inbound KERI traffic to castellan. |

## Why two Dockerfiles

`castellan` and `rack` are separate Python packages maintained in separate repos.
`docker/Dockerfile` builds castellan from this repo's own `pyproject.toml`/`src`.
`docker/Dockerfile.rack` installs `rack` from the wheel vendored at `rack/rack-1.2.0-py3-none-any.whl`
(rack isn't published to a package index castellan can pull from). Both images share the
`keri_data` volume, but each opens its own keystore by name (`castellan` vs `castellan-rack`)
within it — `rack start` only ever does `hby.habByName("rack")` against its own keystore, it
never reads castellan's Habery directly. Keeping them as separate keystores (rather than
`rack` as an alias inside the `castellan` keystore) matters: `castellan` and `castellan-rack`
are separate container processes, and LMDB's locking isn't safe for two processes in
different PID namespaces to hold the same environment open concurrently — sharing one
keystore between them reliably fails with `mdb_txn_begin: Resource temporarily unavailable`.

## Why an init container instead of supervisord

The original nightingale deployment ran ~13 processes (witness/watcher networks, hkapi,
kourier, castellan, etc.) inside one container managed by `supervisord`, because it was
standing up an entire simulated network. Castellan only has three long-running processes,
so each gets its own container — the standard Docker practice of one process per container.
`castellan start` requires its KERI identifier to already exist (it raises a
`ConfigurationError` otherwise), so `castellan-init` runs once via `depends_on:
condition: service_completed_successfully` before `castellan` or `castellan-rack` start.

## Config

`docker/conf/keri/cf/castellan-loadbalancer.json` is rack's resolver config — it tells rack
which MongoDB database to consult to route inbound requests. It's mounted read-only into
`castellan-rack` rather than baked into the image, so it can be edited without a rebuild.

## Ports

- `5923` — rack's inbound ESSR (encrypted) traffic port.
- `5925` — castellan's HTTP API.
- `5927` — castellan's OOBI service.
- `5885` — rack's Prometheus metrics endpoint.