# Deploying the `castellan` chart

This is a field guide to `values.yaml` for standing up a pilot deployment. It assumes you
already have:

- A Kubernetes cluster with a working default `StorageClass` (or you know the name of one).
- Your own MongoDB instance reachable from the cluster.
- An Ingress object of your own (or you're about to write one) that will point at this chart's
  OOBI service.
- Your own external L4 load balancer that will route to `castellan-rack`'s pods directly, by
  label selector — not through this chart's Service.

It does not cover installing the chart on a disposable test cluster from scratch — see
`../../chart-deployment-testing/README.md` for that (EKS-specific, throwaway Mongo, etc). This
doc is about the `values.yaml` fields you need to fill in for a real pilot.

## What gets deployed

- **`<release>` Deployment** — one pod, two containers (`castellan` + `castellan-rack`) sharing a
  PID namespace and an LMDB-backed PVC. Hardcoded to `replicas: 1` — this cannot scale
  horizontally, by design.
- **`<release>-oobi` Deployment** — stateless HTTP service that resolves the `rack` AID's
  location for external KERI parties. Defaults to 2 replicas.
- **`<release>-init` Job** — a `pre-install,pre-upgrade` hook that provisions the `rack` AID
  (identity, end-role, TCP location) in the shared keystore. Runs once, then no-ops on every
  future install against the same PVC. **This is why `rack.externalLocation.host` must be
  correct before your very first `helm install`** — see the dedicated section below.
- **`<release>-keri-data` PVC** — the shared LMDB keystore. Survives `helm uninstall` (see
  `persistence.keep`).

## Required fields — the chart will not install without these

| Field | What it is |
|---|---|
| `image.castellan.repository` / `image.castellan.tag` | Where to pull the `castellan` image from. Empty by default. |
| `image.rack.repository` / `image.rack.tag` | Where to pull the `castellan-rack` image from. Empty by default. |
| `mongodb.connectionString.secretName` | Name of a **pre-existing** Secret in the release namespace holding your Mongo connection string. You create this yourself against your own Mongo instance (see below) — the chart never creates it. |
| `rack.externalLocation.host` | The externally-resolvable hostname/domain for `castellan-rack`'s TCP endpoint — the one your own L4 load balancer already answers to. This gets baked into the KERI keystore on first install and is effectively **immutable** after that (see below). |

If any of these are missing, `helm install`/`helm template` fails fast with a `required(...)`
error rather than deploying something broken.

## Your MongoDB instance

The chart never talks to Mongo directly to create databases or users — it only reads connection
info from Secrets you create ahead of time.

1. **Connection string secret** (required):
   ```bash
   kubectl create secret generic castellan-mongo-conn \
     --from-literal=connection-string='mongodb://your-mongo-host:27017'
   ```
   Then set:
   ```yaml
   mongodb:
     connectionString:
       secretName: castellan-mongo-conn   # the secret name above
       secretKey: "connection-string"     # default; change only if your secret uses a different key
   ```
   Despite the env var this ends up as (`MONGODB_HOST`), the value is the **full connection
   string** (`mongodb://host:port`, or a full SRV/`mongodb+srv://...` URI, or with credentials
   embedded if you're doing it that way instead — see below), not just a bare hostname.

2. **Credentials secret** (optional — only if your Mongo requires auth and you're not embedding
   credentials in the connection string above). You've already created this secret against your
   own Mongo instance — the chart doesn't create it, it just needs to know its name and which
   keys inside it hold the username and password:
   ```yaml
   mongodb:
     credentials:
       secretName: your-existing-mongo-creds-secret   # leave "" to skip auth entirely
       usernameKey: "username"                        # key in that secret holding the username
       passwordKey: "password"                        # key in that secret holding the password
   ```
   `usernameKey`/`passwordKey` default to `"username"`/`"password"` — only change them if your
   existing secret uses different key names (e.g. a secret created with
   `--from-literal=mongo-user=...` needs `usernameKey: mongo-user`).

   Leaving `secretName` empty means the chart emits no `CASTELLAN_DB_USER`/`CASTELLAN_DB_PASS`
   env vars at all — it's not a "connect with blank credentials" mode, it's "don't send
   credentials" (use this if you're embedding credentials directly in the connection string
   instead, or if your Mongo has no auth).

3. **Database name** — `mongodb.databaseName` (default `castellan`). Only change this if you want
   castellan to use a non-default database name on your Mongo instance.

## Rack's external TCP endpoint

`castellan-rack` speaks raw TCP (ESSR), not HTTP, on port 5923 (`ports.rack`). Since you already
have your own external load balancer routing to the pods directly:

- Leave `rack.service.type` as the default `ClusterIP` — you don't need the chart to create a
  `LoadBalancer` Service, and doing so would fight with your own LB for ownership of that
  endpoint.
- Point your load balancer's backend/target group at pods matching these labels (standard for
  any release of this chart; substitute your actual release name):
  ```yaml
  app.kubernetes.io/name: castellan
  app.kubernetes.io/instance: <your-release-name>
  app.kubernetes.io/component: castellan
  ```
  targeting port `5923` (or whatever you set `ports.rack` to). `../../chart-deployment-testing/
  nlb-service.yaml` is a worked example of exactly this pattern (AWS-specific, but the shape — a
  standalone Service with this selector, applied outside Helm — is what you're replicating with
  your own LB).
- Set `rack.externalLocation.host` to the hostname your load balancer already answers to (its DNS
  name, or a CNAME/A record you've pointed at it). Leave `rack.externalLocation.port` empty
  unless your external endpoint listens on a different port than `ports.rack` — it defaults to
  matching.

**This value is effectively write-once.** `castellan-init` only provisions the `rack` AID's
location the very first time it runs against a given keystore/PVC; a later `helm upgrade` with a
different `rack.externalLocation.host` silently no-ops (the AID already exists, so the whole
provisioning block is skipped). Get the load balancer's hostname finalized *before* your first
`helm install`. If you need to change it later, the only path is deleting the
`<release>-keri-data` PVC and reinstalling clean — there's no in-place update.

`rack.httpHost` (default `127.0.0.1`) is unrelated to this — it's how `castellan-rack` reaches
`castellan` over loopback inside the shared pod. Leave it alone.

## OOBI ingress (your existing Ingress object)

The chart can optionally create an `Ingress` for the OOBI service itself
(`castellanOobi.ingress.enabled: true`, plus `className`/`host`/`annotations`/`tls`) — but since
you're bringing your own Ingress object, leave `castellanOobi.ingress.enabled: false` (the
default) so the chart doesn't create a competing one. Point your existing Ingress at:

- Service name: `<release-name>-oobi` (or `<release-name>` if your release name already contains
  `castellan` — see `castellan.fullname` in `_helpers.tpl` if you want the exact rule)
- Port: `ports.oobi` (default `5927`)

That's the HTTP endpoint external KERI parties hit to resolve the `rack` AID's location
(`GET /oobi/server`) — it's plain HTTP, so it's ingress-friendly, unlike the rack TCP port above.

`castellanOobi.service.type` can stay `ClusterIP` (default) — that's what a normal Ingress
backend expects.

## Everything else (sane defaults — only touch if you know why)

| Field | Default | When to change it                                                                                                                                              |
|---|---|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `ports.*` | `castellan:5925`, `rack:5923`, `rackMetrics:5885`, `oobi:5927` | Only if something else on your nodes conflicts. Must match whatever you configured your external LB/Ingress to target.                                         |
| `imagePullSecrets` | `[]` | If your image registry is private. It should not be for the purposes of this pilot                                                                             |
| `persistence.storageClassName` | `""` (cluster default) | Set explicitly if your cluster has no default `StorageClass`, or you want a specific one.                                                                      |
| `persistence.size` | `10Gi` | Bump if you expect a large keystore.                                                                                                                           |
| `persistence.accessMode` | `ReadWriteOnce` | Leave alone — the pod topology requires RWO.                                                                                                                   |
| `persistence.keep` | `true` | Keeps the PVC (and its `helm.sh/resource-policy: keep`) on `helm uninstall`. Set `false` only if you're fine losing the keystore on uninstall.                 |
| `castellanOobi.replicaCount` | `2` | Scale up/down for OOBI traffic; stateless, safe to change anytime.                                                                                             |
| `castellan.resources` / `rack.resources` / `castellanOobi.resources` | `{}` (no limits) | Set standard Kubernetes `requests`/`limits` once you know the pilot's actual load.                                                                             |
| `castellan.extraEnv` | `[]` | Extra env vars for the `castellan` container, if castellan needs app-specific config beyond what this chart sets.                                              |
| `rack.metricsService.type` / `.annotations` | `ClusterIP` | Prometheus scrape target for `castellan-rack`. Keep off any public LB; only change if your Prometheus needs a different Service type/annotations to scrape it. |
| `castellanInit.backoffLimit` / `.activeDeadlineSeconds` | `3` / `300` | Raise `activeDeadlineSeconds` only if the init Job is timing out for a legitimate reason (e.g. slow storage provisioning).                                     |
| `serviceAccount.create` / `.name` | `false` / `""` | Leave as-is unless your cluster's RBAC policy requires workloads to use a dedicated, non-default ServiceAccount.                                               |

## Minimal `values.yaml` overlay for a pilot

Putting the required + your-infra fields together:

```yaml
image:
  castellan: {repository: "healthkeri/castellan", tag: "<pinned-tag>"}
  rack:      {repository: "healthkeri/castellan-rack", tag: "<pinned-tag>"}

mongodb:
  connectionString:
    secretName: castellan-mongo-conn
  credentials:
    secretName: your-existing-mongo-creds-secret   # omit entirely if your Mongo has no auth
    usernameKey: "username"                        # match your existing secret's key names
    passwordKey: "password"

rack:
  externalLocation:
    host: rack.your-domain.example      # your existing external LB's hostname

persistence:
  storageClassName: your-storage-class  # omit if your cluster has a default
```

Validate before installing:
```bash
helm lint charts/castellan -f your-values.yaml
helm template castellan charts/castellan -f your-values.yaml | less
```
