# Testing the castellan and witness-hk Helm charts on EKS

This directory holds everything needed to stand up a single disposable EKS cluster and verify
both `charts/castellan` and `charts/witness-hk` deploy and run correctly, end to end — including
that each is actually reachable from outside the cluster, the precondition for real KERI parties
to talk to either of them. It's a scratch/smoke-test environment for one combined POC, not a
staging or production config — MongoDB runs unauthenticated in-cluster, and witness-hk's TLS is
self-signed against a magic-DNS hostname rather than a domain you own. Two standalone manifests
(`nlb-service.yaml` for castellan-rack, `ingress-nginx` for witness-hk — the latter installed via
its own Helm chart, not a manifest in this directory) provision real external entry points and are
installed as part of the normal walkthrough below, not as optional add-ons.

Both charts are installed into the same cluster and namespace — there's no runtime coupling
between them (separate LMDB keystores, separate PVCs), so sharing infrastructure for a POC is
just cost/effort savings, not a statement about how they'd be deployed for real.

All commands below assume your shell's working directory is the **repo root**.

## Files in this directory

| File | Purpose |
|---|---|
| `cluster.yaml` | `eksctl` config for the disposable test cluster (1 node, EBS CSI driver pre-wired via IRSA). |
| `storageclass-gp3-csi.yaml` | Default `StorageClass` backed by the EBS CSI driver — EKS doesn't ship a working one out of the box (see gotcha below). |
| `values-castellan.yaml` | Helm values for castellan in this test environment (Docker Hub images, the test Mongo secret). Its `rack.externalLocation.host` placeholder is overridden at install time with the real NLB hostname — see [Spin up](#spin-up) and [Install](#install). |
| `values-witness-hk.yaml` | Helm values for witness-hk in this test environment (Docker Hub image, ingress enabled). Its `baseDomain` is deliberately unset — overridden at install time with the sslip.io hostname derived from ingress-nginx's NLB IP, since that IP doesn't exist until ingress-nginx is installed — see [Spin up](#spin-up) and [Install](#install). |
| `nlb-service.yaml` | Standalone (non-Helm) Service that exposes `castellan-rack` via a real AWS NLB. Applied during [Spin up](#spin-up), deliberately outside the chart/release — see that step for why. |

witness-hk's external entry point (`ingress-nginx`) isn't a file in this directory — it's a
third-party Helm chart installed directly (`helm install ingress-nginx ingress-nginx/ingress-nginx
...`), same as `helm`/`eksctl`/`kubectl` are tools you install rather than files this repo ships.

## Prerequisites

- An AWS account/credentials with permission to create EKS clusters, CloudFormation stacks, IAM
  roles, and EC2 instances (`aws sts get-caller-identity` should succeed).
- CLI tools: `awscli`, `eksctl`, `kubectl`, `helm`, `dig`, `openssl`. On macOS:
  `brew install awscli eksctl kubectl helm bind openssl` (`dig`/`openssl` usually already exist,
  `brew install` is a no-op if so).
- Docker Hub images already published:
  - `healthkeri/castellan` and `healthkeri/castellan-rack` — see `.github/workflows/build-push.yml`
    for how they're built, or build/push manually with `docker build -f docker/Dockerfile .` /
    `docker build -f docker/Dockerfile.rack .` if you need to test unpublished changes.
  - `healthkeri/witness-hk` (currently tag `v1.3.6-dev`, built manually — see
    `charts/witness-hk/README.md` and the top-level plan for how it was published; there's no CI
    for this image yet).

**Cost warning:** an EKS control plane bills continuously from the moment it's created
(~$0.10/hr as of this writing), plus the EC2 node(s), EBS volumes (one for castellan's shared
keystore, one per witness-hk replica), and **two** NLBs provisioned during Spin up (one for
`castellan-rack`, one for `ingress-nginx` fronting witness-hk). Don't leave the cluster up longer
than you're actively testing — see [Spin down](#spin-down) below.

## Spin up

**1. Create the cluster** (takes roughly 15-20 minutes — EKS control plane creation dominates):
```bash
eksctl create cluster -f chart-deployment-testing/cluster.yaml
```
This provisions the EKS control plane, one managed node, and the `aws-ebs-csi-driver` addon with
an IRSA role already attached (via `wellKnownPolicies.ebsCSIController`). It also points your
local kubeconfig at the new cluster automatically. Confirm:
```bash
kubectl config current-context   # should be castellan-admin@castellan-test.us-east-1.eksctl.io
kubectl get nodes                # should show 1 Ready node
eksctl get addon --cluster castellan-test --region us-east-1   # aws-ebs-csi-driver should be ACTIVE
```

**2. Apply the default StorageClass.** This is required and easy to miss — see
[Gotcha: PVC stuck Pending](#gotcha-pvc-stuck-pending) for why:
```bash
kubectl apply -f chart-deployment-testing/storageclass-gp3-csi.yaml
kubectl get storageclass   # gp3-csi should show "(default)"
```

**3. Create the namespace** (shared by both charts):
```bash
kubectl create namespace castellan-test
```

**4. Provision the real AWS NLB for castellan-rack, before installing the app.**
`castellan-init` only ever provisions the `rack` AID's location once per keystore — see
[Gotcha: `rack.externalLocation.host` can't be changed after first
install](#gotcha-rackexternallocationhost-cant-be-changed-after-first-install). Provisioning the
NLB first means the very first `helm install` below can bake in the real, final hostname, so you
never need to wipe the keystore and reinstall just to get a working external address:
```bash
kubectl apply -f chart-deployment-testing/nlb-service.yaml
kubectl get svc castellan-rack-nlb -n castellan-test -w   # wait for EXTERNAL-IP to populate
NLB_HOST=$(kubectl get svc castellan-rack-nlb -n castellan-test \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "$NLB_HOST"
```
`nlb-service.yaml` selects the same pod labels the chart's Deployment produces, so the NLB starts
routing as soon as those pods exist — it doesn't need the app installed first. Note `$NLB_HOST`
down and reuse it for the rest of this testing session; it stays stable for as long as
`castellan-rack-nlb` exists, unaffected by any `helm install`/`upgrade`/`uninstall` of the
`castellan` release.

**Why a standalone Service instead of a chart values overlay:** in a real deployment, whoever
stands up the TCP ingress owns that infrastructure separately from this chart, and already knows
the domain they've assigned it *before* installing castellan — the chart only ever needs to
receive that value once, correctly, on the very first install. This test mirrors that ordering by
keeping the NLB's lifecycle **entirely outside the Helm release**: `nlb-service.yaml` is a plain
Kubernetes manifest (not a chart template), applied and torn down via `kubectl` directly. `helm
install`/`helm uninstall`/`helm upgrade` of the `castellan` release never touches it, so you can
wipe the keystore and reinstall the app as many times as you want without ever losing the NLB or
getting a new hostname — this is *not* possible if the chart's own Service is made `LoadBalancer`
(its NLB is deleted the moment `helm uninstall` deletes the Service, and a fresh `helm install`
gets a new one with a different hostname — confirmed live while developing this test).

**5. Stand up a throwaway MongoDB** (no auth — fine for this smoke test, not representative of a
real deployment, which uses Greg's externally-hosted, credentialed MongoDB):
```bash
kubectl -n castellan-test create deployment mongodb --image=mongo:8.0
kubectl -n castellan-test expose deployment mongodb --port=27017
kubectl -n castellan-test rollout status deploy/mongodb
```

**6. Create the Mongo connection secret** the chart expects
(`mongodb.connectionString.secretName` in `values-castellan.yaml`):
```bash
kubectl -n castellan-test create secret generic castellan-mongo-conn \
  --from-literal=connection-string='mongodb://mongodb:27017'
```
No `mongodb.credentials.secretName` secret is needed here since this test Mongo has no auth —
leaving that value unset in `values-castellan.yaml` is what makes the chart skip emitting
`CASTELLAN_DB_USER`/`CASTELLAN_DB_PASS` entirely (see `_helpers.tpl`'s `castellan.mongoEnv`).

**7. If your Docker Hub images are private**, add a pull secret and reference it as
`imagePullSecrets` in the relevant values file:
```bash
kubectl -n castellan-test create secret docker-registry dockerhub-creds \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username=<user> --docker-password=<token>
```
(Not needed for the `healthkeri/*` images as configured, if they're public.)

**8. Install `ingress-nginx`**, witness-hk's external entry point. Requesting an NLB (rather than
the classic ELB ingress-nginx defaults to on AWS) matters here because NLBs get static per-AZ IPs
— this single-node/single-AZ cluster gets exactly one, which step 9 needs to be stable for the
life of the test:
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"=nlb \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-cross-zone-load-balancing-enabled"=true
kubectl get svc ingress-nginx-controller -n ingress-nginx -w   # wait for EXTERNAL-IP (a hostname) to populate
```
Give the admission webhook a minute to become ready after this — see [Gotcha: `failed calling
webhook` right after installing
ingress-nginx](#gotcha-failed-calling-webhook-right-after-installing-ingress-nginx) if
[Install](#install)'s witness-hk step hits it.

**9. Derive a real, resolvable hostname for witness-hk without owning a domain.** NLBs report a
hostname, not an IP, in `status.loadBalancer.ingress` — resolve it once to get the static IP, then
build an [sslip.io](https://sslip.io) hostname from it. `sslip.io` (and its mirror `nip.io`)
resolve `<anything>.<ip-with-dashes>.sslip.io` to `<ip>` for any IP, with no registration needed —
exactly the wildcard DNS behavior witness-hk's chart expects from a real domain, without one:
```bash
INGRESS_HOST=$(kubectl get svc ingress-nginx-controller -n ingress-nginx \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
INGRESS_IP=$(dig +short "$INGRESS_HOST" | head -1)
BASE_DOMAIN="${INGRESS_IP//./-}.sslip.io"
echo "$BASE_DOMAIN"   # e.g. 34-201-88-12.sslip.io
```
If `dig` returns nothing, DNS for the newly-created NLB hasn't propagated yet — wait 30-60 seconds
and retry. Note `$BASE_DOMAIN` down; you'll need it for [Install](#install) and every `curl` in
[Verify](#verify).

**10. Generate a self-signed wildcard cert for `$BASE_DOMAIN`.** This is a POC-only stand-in for a
real cert — see the [Ingress and TLS](../charts/witness-hk/README.md#ingress-and-tls) section of
the chart's own README for the production recommendation (a real wildcard cert covering your own
domain):
```bash
openssl req -x509 -nodes -days 30 -newkey rsa:2048 \
  -keyout /tmp/witness-tls.key -out /tmp/witness-tls.crt \
  -subj "/CN=*.${BASE_DOMAIN}" -addext "subjectAltName=DNS:*.${BASE_DOMAIN}"
kubectl -n castellan-test create secret tls witness-wildcard-tls \
  --cert=/tmp/witness-tls.crt --key=/tmp/witness-tls.key
rm /tmp/witness-tls.key /tmp/witness-tls.crt
```

## Install

Validate before touching the cluster:
```bash
helm lint charts/castellan -f chart-deployment-testing/values-castellan.yaml
helm template castellan charts/castellan -f chart-deployment-testing/values-castellan.yaml | less
helm lint charts/witness-hk -f chart-deployment-testing/values-witness-hk.yaml \
  --set baseDomain="$BASE_DOMAIN"
helm template witness-hk charts/witness-hk -f chart-deployment-testing/values-witness-hk.yaml \
  --set baseDomain="$BASE_DOMAIN" | less
```

Install castellan with the real NLB host from [Spin up](#spin-up) step 4 baked in from the
start — this is what lets the reachability checks in [Verify](#verify) below pass without a
second install:
```bash
helm install castellan charts/castellan -n castellan-test \
  -f chart-deployment-testing/values-castellan.yaml \
  --set rack.externalLocation.host="$NLB_HOST"
```
`STATUS: deployed` in the output means the `castellan-init` pre-install hook Job already ran to
completion — Helm won't report success otherwise. If it fails, see
[Troubleshooting](#troubleshooting) below before retrying.

Install witness-hk with the `$BASE_DOMAIN` from [Spin up](#spin-up) step 9:
```bash
helm install witness-hk charts/witness-hk -n castellan-test \
  -f chart-deployment-testing/values-witness-hk.yaml \
  --set baseDomain="$BASE_DOMAIN"
```
Unlike castellan's `rack.externalLocation.host`, witness-hk's per-replica hostname is **not**
write-once — `docker/scripts/witopnet.sh` regenerates `witopnet.json` from
`WITOPNET_BASE_DOMAIN` on every container start (confirmed by reading the script — it's an
unconditional `cat > ... <<EOF` on each boot, not a first-run-only provisioning step). If you ever
need to change `$BASE_DOMAIN` in this test environment (e.g. `ingress-nginx`'s NLB got recreated
with a new IP), `helm upgrade --set baseDomain=<new-domain>` followed by a rollout restart is
enough — no keystore wipe required, unlike castellan-rack's host.

## Verify

**Pods up, nothing crash-looping:**
```bash
kubectl get pods -n castellan-test -o wide
```
Expect `castellan-<hash>` (2/2 ready — `castellan` + `castellan-rack` containers), two
`castellan-oobi-<hash>` pods (1/1 each), and `witness-hk-0`/`witness-hk-1`/`witness-hk-2` (1/1
each).

**Logs** (see the [init Job log gotcha](#gotcha-init-job-logs-disappear-on-success) first):
```bash
kubectl logs -n castellan-test deploy/castellan -c castellan
kubectl logs -n castellan-test deploy/castellan -c castellan-rack
kubectl logs -n castellan-test deploy/castellan-oobi
kubectl logs -n castellan-test witness-hk-0
```

**Mongo Access**
```bash
kubectl exec -it -n castellan-test deploy/mongodb -- mongosh
```

**Confirm `shareProcessNamespace` is actually working** — this is the load-bearing part of the
whole two-container-one-pod design (see `charts/castellan/templates/deployment-castellan.yaml`'s
comments and `docker/README.md` for why): from inside the `castellan-rack` container, both
processes should be visible.
```bash
kubectl exec -n castellan-test deploy/castellan -c castellan-rack -- ps aux
```

**Restart-stress test** — a single clean start doesn't prove the LMDB PID-sharing fix holds up;
the original bug only appeared once `castellan` had been running a while:
```bash
for i in {1..5}; do
  kubectl -n castellan-test delete pod -l app.kubernetes.io/component=castellan
  kubectl -n castellan-test wait --for=condition=ready pod -l app.kubernetes.io/component=castellan --timeout=120s
  kubectl -n castellan-test logs deploy/castellan -c castellan-rack --tail=100 | grep -qi mdb_txn_begin \
    && echo "FAIL: $i" || echo "ok: $i"
done
```

**OOBI resolution:**
```bash
kubectl -n castellan-test port-forward svc/castellan-oobi 5927:5927 &
curl http://127.0.0.1:5927/oobi/server
```
Should return the `rack` AID with the `rack.externalLocation.host` value — i.e. `$NLB_HOST` from
[Spin up](#spin-up) step 4, since that's what [Install](#install) baked in, not the placeholder
from `values-castellan.yaml`.

**castellan-rack reachability from outside the cluster.** The checks above only prove
`castellan-rack`'s port is reachable *inside* the cluster (`rack.service.type: ClusterIP`, the
production default too). This confirms it's also reachable from outside — the precondition for
real KERI parties to open ESSR sessions with it. Run this from your own machine, not from inside a
pod:
```bash
nc -zv "$NLB_HOST" 5923
```
A successful TCP connect (or immediate close, since nothing has sent a valid ESSR frame) confirms
Layer 4 reachability through `castellan-rack-nlb` (provisioned in [Spin up](#spin-up) step 4).
`connection refused`/`timed out` means the NLB, its target group, or the node security group isn't
routing traffic through yet — give the NLB a minute or two after `EXTERNAL-IP` appeared, since AWS
provisioning lags slightly behind the Kubernetes object.

**witness-hk's boot API (in-cluster only — never exposed via Ingress by design):**
```bash
kubectl exec -n castellan-test witness-hk-0 -- curl -s -i localhost:5631/health   # expect 204
```

**witness-hk reachability from outside the cluster, per replica.** This is the equivalent check to
castellan-rack's `nc -zv` above, but over real HTTPS through `ingress-nginx` rather than raw TCP
through a hand-applied NLB — proving the exact path a real KERI controller resolving a witness's
`curls` entry would take. `-k` is required because the cert from [Spin up](#spin-up) step 10 is
self-signed; a `405` is the expected response (the witness server's Falcon resource is POST-only,
confirmed live during Part 1's container testing — a `405` proves the app is up and the request
reached it, not that anything is broken):
```bash
for i in 0 1 2; do
  echo "witness-$i:"
  curl -sk -o /dev/null -w '%{http_code}\n' "https://witness-$i.${BASE_DOMAIN}/"
done
```

**Not testable in this environment:** neither check above confirms a full protocol handshake
(ESSR for castellan-rack, KERI witnessing for witness-hk) succeeds end-to-end — that needs a real
external party actually attempting the exchange, which depends on Greg's ingress setup for the
real cluster and can't be exercised here. Actually provisioning a witness identity via witness-hk's
boot API (`POST /witnesses`) is also out of scope for this chart-deployment walkthrough — see the
top-level plan's Part 2 notes on why that stays an external, runtime concern.

## Account Creation (castellan)

The chart mounts a helper script, rendered from `charts/castellan/templates/configmap-castellan-account.yaml`,
into the `castellan` container at `docker/scripts/castellan-account.sh`. It wraps `castellan account
create` for the common case of registering an account against the credentials this release is
already configured with, without needing to retype the Mongo connection details by hand.

`--name`/`--alias` are hardcoded to `castellan` — this pod only ever manages the one keystore — but
`--dbhost`/`--dbname`/`--dbuser`/`--dbpass` default to whatever `MONGODB_HOST`/`CASTELLAN_DB_NAME`/
`CASTELLAN_DB_USER`/`CASTELLAN_DB_PASS` are already set to in the `castellan` container's
environment (populated from `values-castellan.yaml`'s `mongodb.*` settings via `_helpers.tpl`'s
`castellan.mongoEnv` — the same env vars `docker/scripts/castellan.sh` itself reads). Passing a flag
overrides its corresponding default; a flag is only omitted from the underlying `castellan account
create` call if both the flag and the matching env var are unset (e.g. `CASTELLAN_DB_USER`/
`CASTELLAN_DB_PASS` when this release's Mongo has no auth — see [Spin up](#spin-up) step 6).

Run it interactively, since it prompts for the account username and OOBI:
```bash
kubectl exec -it -n castellan-test deploy/castellan -c castellan -- \
  bash docker/scripts/castellan-account.sh
```
It will prompt:
```
Enter the account username:
Enter the account OOBI:
```

To point at a different database than this release's own — e.g. testing against a second Mongo —
override any subset of the flags:
```bash
kubectl exec -it -n castellan-test deploy/castellan -c castellan -- \
  bash docker/scripts/castellan-account.sh --dbhost mongodb://other-mongo:27017 --dbname castellan
```

## Spin down

```bash
helm uninstall castellan -n castellan-test
helm uninstall witness-hk -n castellan-test
kubectl delete pvc castellan-keri-data -n castellan-test           # not deleted by uninstall -- see gotcha below
kubectl delete pvc -n castellan-test -l app.kubernetes.io/name=witness-hk   # StatefulSet PVCs, also not deleted by uninstall
kubectl delete secret witness-wildcard-tls -n castellan-test
helm uninstall ingress-nginx -n ingress-nginx
kubectl delete namespace ingress-nginx
kubectl delete namespace castellan-test
kubectl delete -f chart-deployment-testing/nlb-service.yaml
eksctl delete cluster --region=us-east-1 --name=castellan-test
```
`kubectl delete namespace castellan-test` also removes `castellan-rack-nlb` (provisioned in [Spin
up](#spin-up) step 4) — it's namespace-scoped even though it's not Helm-managed. If you're
stopping short of a full spin-down but are done with the NLBs specifically, tear them down on
their own first with `kubectl delete -f chart-deployment-testing/nlb-service.yaml` (castellan-rack)
and `helm uninstall ingress-nginx -n ingress-nginx` (witness-hk) so they don't keep billing.

The last step tears down the CloudFormation stacks (nodegroup + control plane) and stops billing.
It takes a few minutes; `eksctl` will wait for it.

## Start over from scratch

Spin down fully (above), then repeat [Spin up](#spin-up) → [Install](#install). Nothing here is
stateful across a full `eksctl delete cluster` — a fresh cluster has no leftover PVC, no leftover
failed Helm release, no stale `castellan-init` Job, and no stale `$BASE_DOMAIN` to worry about
(the new `ingress-nginx` install gets a new NLB IP, so recompute it fresh — see [Spin
up](#spin-up) step 9).

## Troubleshooting

These are real issues hit while first standing this up — not hypothetical.

### Gotcha: `rack.externalLocation.host` can't be changed after first install
`docker/scripts/castellan-init.sh` only provisions the `rack` AID (including its end-role and
location records) the first time it runs against a given keystore — once the AID exists, the whole
block is skipped, including `kli location add`. A later `helm upgrade --set
rack.externalLocation.host=...` against a surviving keystore/PVC will **not** update the location:
the init Job still runs (it's a `pre-install,pre-upgrade` hook), but it silently no-ops since the
`rack` AID already exists.

This is intentional for now, not an oversight: in a real deployment, whoever provisions the TCP
ingress already knows the domain beforehand, so the chart only ever needs the correct value once,
on the very first install. [Spin up](#spin-up) step 4 provisions the NLB *before* [Install](#install)
for exactly this reason — the walkthrough above only ever needs one `helm install`. If you still
need to change the host afterward in this test environment — a new NLB, a typo, anything — you
must wipe the keystore and reinstall clean:
```bash
helm uninstall castellan -n castellan-test
kubectl delete pvc castellan-keri-data -n castellan-test
helm install castellan charts/castellan -n castellan-test \
  -f chart-deployment-testing/values-castellan.yaml \
  --set rack.externalLocation.host="<new-host>"
```
There is no supported update path short of this. witness-hk's `baseDomain` does **not** have this
problem — see [Install](#install) for why.

### Gotcha: PVC stuck `Pending`
Symptom: `kubectl get pvc -n castellan-test` shows a PVC (e.g. `castellan-keri-data`, or one of
witness-hk's `keri-data-witness-hk-N`) stuck `Pending`, with `kubectl get events` showing `no
persistent volumes available for this claim and no storage class is set`.

Cause: both charts' `persistence.storageClassName` defaults to `""`, which relies on the cluster
having a StorageClass marked default. A stock EKS cluster ships a `gp2` class using the **legacy
in-tree** `kubernetes.io/aws-ebs` provisioner, which is not marked default and — more importantly
— no longer has a working controller behind it on current Kubernetes versions (in-tree EBS support
was removed after CSI migration completed). Installing the `aws-ebs-csi-driver` addon does *not*
automatically create a StorageClass either; you have to apply one yourself, which is what
`storageclass-gp3-csi.yaml` is for. This is why it's a required step in [Spin up](#spin-up), not
optional cleanup.

### Gotcha: `Error: configmap "castellan-env" not found` in the init Job
This was an actual bug in the chart (fixed in `charts/castellan/templates/configmap-env.yaml`,
now carries `helm.sh/hook: pre-install,pre-upgrade` annotations). Helm runs all `pre-install`
hooks to completion *before* applying any normal resource — `castellan-init` is a hook Job that
reads this ConfigMap via `envFrom`, so the ConfigMap had to become a hook too (ordered ahead of
the Job via `helm.sh/hook-weight`), or it didn't exist yet when the Job ran. If you ever see this
error again, it means something reintroduced a non-hook resource that a hook resource depends on
— `helm lint`/`helm template` cannot catch this class of bug, since neither simulates multi-phase
hook execution.

### Gotcha: `cannot reuse a name that is still in use`
After a failed `helm install`, Helm still records the release (in `failed` status) as a Secret in
the namespace. `helm list -n castellan-test` will show it; `helm uninstall <release> -n
castellan-test` clears it before you can reinstall under the same name.

### Gotcha: stale `castellan-init` Job/PVC block a retry
`castellan-init` (`job-castellan-init.yaml`) and castellan's PVC (`pvc-keri-data.yaml`) are both
`helm.sh/hook` resources, which `helm uninstall` does **not** clean up (that's intentional for the
PVC — see `persistence.keep` — so real keystore data survives an uninstall). Two different
policies apply:
- The **Job** has `helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded` — Helm deletes
  it automatically before creating a new one, but only on success; a *failed* run is left in place
  on purpose so you can inspect it. Delete it manually before retrying:
  `kubectl delete job castellan-init -n castellan-test`.
- The **PVC** deliberately has *no* delete policy (deleting-then-recreating it on every install
  would destroy the real LMDB keystore, since `gp3-csi`'s reclaim policy is `Delete`). This means
  if a PVC survives an uninstall (by design) and you try to `helm install` again, Helm's hook
  `Create()` will fail with "already exists" — there's currently no automatic recovery from this;
  if the PVC has no data you care about yet, `kubectl delete pvc castellan-keri-data -n
  castellan-test` before reinstalling. This is a known rough edge in the current design, not
  something to paper over by adding a destructive delete policy. witness-hk's `volumeClaimTemplates`
  PVCs aren't hook-managed at all (StatefulSets own their PVC lifecycle directly), so this specific
  gotcha is castellan-only.

### Gotcha: init Job logs disappear on success
Because of the `hook-succeeded` delete policy above, `kubectl logs -l
app.kubernetes.io/component=castellan-init` will usually return nothing after a successful
`helm install` — the Job and its pod are already gone by the time the command returns. That's
expected, not a bug: `STATUS: deployed` from `helm install` is itself the proof it succeeded. If
you need to inspect a successful run's logs, temporarily remove `hook-succeeded` from the policy
in `job-castellan-init.yaml` before that one install.

### Gotcha: `failed calling webhook` right after installing ingress-nginx
Symptom: applying an Ingress (or `helm install witness-hk` with `ingress.enabled: true`) right
after [Spin up](#spin-up) step 8 fails with something like `Internal error occurred: failed
calling webhook "validate.nginx.ingress.kubernetes.io"`.

Cause: `ingress-nginx`'s admission webhook pod needs a few seconds to become ready and register
after the chart installs; anything that creates an `Ingress` object before then gets rejected.
Wait for the webhook pod, then retry:
```bash
kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=admission-webhook \
  -n ingress-nginx --timeout=60s
```

### Gotcha: `dig` returns no answer for the ingress-nginx NLB hostname
Symptom: [Spin up](#spin-up) step 9's `dig +short "$INGRESS_HOST"` returns empty, so
`$BASE_DOMAIN` ends up as `.sslip.io` (missing the IP).

Cause: DNS for a newly-created NLB takes a short time to propagate after `EXTERNAL-IP` first shows
a hostname in `kubectl get svc`. Wait 30-60 seconds and re-run the `dig` command; it's not
necessary to recreate anything.

### Gotcha: `curl: (60) SSL certificate problem` when checking witness-hk over HTTPS
Expected, not a bug — [Spin up](#spin-up) step 10 generates a self-signed cert for `$BASE_DOMAIN`
(a POC stand-in; there's no real CA-issued cert for an sslip.io wildcard). Every `curl` against a
`witness-N.$BASE_DOMAIN` host in this doc already passes `-k` for this reason; if you're running
one manually (e.g. from a browser or a different tool), you'll need the equivalent
"skip cert verification" option.