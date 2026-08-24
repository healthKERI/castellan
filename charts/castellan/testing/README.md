# Testing the Castellan Helm chart on EKS

This directory holds everything needed to stand up a disposable EKS cluster and verify
`charts/castellan` deploys and runs correctly, end to end. It's a scratch/smoke-test
environment, not a staging or production config — MongoDB runs unauthenticated in-cluster here,
and `rack.externalLocation.host` is a placeholder that's never actually resolved.

All commands below assume your shell's working directory is the **repo root**.

## Files in this directory

| File | Purpose |
|---|---|
| `cluster.yaml` | `eksctl` config for the disposable test cluster (1 node, EBS CSI driver pre-wired via IRSA). |
| `storageclass-gp3-csi.yaml` | Default `StorageClass` backed by the EBS CSI driver — EKS doesn't ship a working one out of the box (see gotcha below). |
| `values.yaml` | Helm values for this test environment (Docker Hub images, the test Mongo secret, placeholder rack location). |

## Prerequisites

- An AWS account/credentials with permission to create EKS clusters, CloudFormation stacks, IAM
  roles, and EC2 instances (`aws sts get-caller-identity` should succeed).
- CLI tools: `awscli`, `eksctl`, `kubectl`, `helm`. On macOS: `brew install awscli eksctl kubectl helm`.
- Docker Hub images already published (currently `healthkeri/castellan` and
  `healthkeri/castellan-rack`) — this doc assumes they exist; see `.github/workflows/build-push.yml`
  for how they're built, or build/push manually with `docker build -f docker/Dockerfile .` /
  `docker build -f docker/Dockerfile.rack .` if you need to test unpublished changes.

**Cost warning:** an EKS control plane bills continuously from the moment it's created
(~$0.10/hr as of this writing) plus the EC2 node(s) and EBS volume. Don't leave the cluster up
longer than you're actively testing — see [Spin down](#spin-down) below.

## Spin up

**1. Create the cluster** (takes roughly 15-20 minutes — EKS control plane creation dominates):
```bash
eksctl create cluster -f charts/castellan/testing/cluster.yaml
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
kubectl apply -f charts/castellan/testing/storageclass-gp3-csi.yaml
kubectl get storageclass   # gp3-csi should show "(default)"
```

**3. Create the namespace:**
```bash
kubectl create namespace castellan-test
```

**4. Stand up a throwaway MongoDB** (no auth — fine for this smoke test, not representative of a
real deployment, which uses Greg's externally-hosted, credentialed MongoDB):
```bash
kubectl -n castellan-test create deployment mongodb --image=mongo:8.0
kubectl -n castellan-test expose deployment mongodb --port=27017
kubectl -n castellan-test rollout status deploy/mongodb
```

**5. Create the Mongo connection secret** the chart expects
(`mongodb.connectionString.secretName` in `values.yaml`):
```bash
kubectl -n castellan-test create secret generic castellan-mongo-conn \
  --from-literal=connection-string='mongodb://mongodb:27017'
```
No `mongodb.credentials.secretName` secret is needed here since this test Mongo has no auth —
leaving that value unset in `values.yaml` is what makes the chart skip emitting
`CASTELLAN_DB_USER`/`CASTELLAN_DB_PASS` entirely (see `_helpers.tpl`'s `castellan.mongoEnv`).

**6. If your Docker Hub images are private**, add a pull secret and reference it as
`imagePullSecrets` in `values.yaml`:
```bash
kubectl -n castellan-test create secret docker-registry dockerhub-creds \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username=<user> --docker-password=<token>
```
(Not needed for the `healthkeri/*` images as configured in `values.yaml` if they're public.)

## Install

Validate before touching the cluster:
```bash
helm lint charts/castellan -f charts/castellan/testing/values.yaml
helm template castellan charts/castellan -f charts/castellan/testing/values.yaml | less
```

Install:
```bash
helm install castellan charts/castellan -n castellan-test -f charts/castellan/testing/values.yaml
```
`STATUS: deployed` in the output means the `castellan-init` pre-install hook Job already ran to
completion — Helm won't report success otherwise. If it fails, see
[Troubleshooting](#troubleshooting) below before retrying.

## Verify

**Pods up, nothing crash-looping:**
```bash
kubectl get pods -n castellan-test -o wide
```
Expect `castellan-<hash>` (2/2 ready — `castellan` + `castellan-rack` containers) and two
`castellan-oobi-<hash>` pods (1/1 each).

**Logs** (see the [init Job log gotcha](#gotcha-init-job-logs-disappear-on-success) first):
```bash
kubectl logs -n castellan-test deploy/castellan -c castellan
kubectl logs -n castellan-test deploy/castellan -c castellan-rack
kubectl logs -n castellan-test deploy/castellan-oobi
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
Should return the `rack` AID with the `rack.externalLocation.host` value from `values.yaml`.

**Not testable in this environment:** an actual ESSR round trip through `castellan-rack`'s
exposed port needs a real, externally-resolvable `rack.externalLocation.host` behind an AWS NLB
(port 5923 is raw TCP, not HTTP/ALB-compatible) — that depends on Greg's ingress setup for the
real cluster and can't be exercised here.

## Spin down

```bash
helm uninstall castellan -n castellan-test
kubectl delete pvc castellan-keri-data -n castellan-test   # not deleted by uninstall -- see gotcha below
kubectl delete namespace castellan-test
eksctl delete cluster --region=us-east-1 --name=castellan-test
```
The last step tears down the CloudFormation stacks (nodegroup + control plane) and stops billing.
It takes a few minutes; `eksctl` will wait for it.

## Start over from scratch

Spin down fully (above), then repeat [Spin up](#spin-up) → [Install](#install). Nothing here is
stateful across a full `eksctl delete cluster` — a fresh cluster has no leftover PVC, no leftover
failed Helm release, and no stale `castellan-init` Job to worry about.

## Troubleshooting

These are real issues hit while first standing this up — not hypothetical.

### Gotcha: PVC stuck `Pending`
Symptom: `kubectl get pvc -n castellan-test` shows `castellan-keri-data` stuck `Pending`, with
`kubectl get events` showing `no persistent volumes available for this claim and no storage class
is set`.

Cause: `charts/castellan/values.yaml`'s `persistence.storageClassName` defaults to `""`, which
relies on the cluster having a StorageClass marked default. A stock EKS cluster ships a `gp2`
class using the **legacy in-tree** `kubernetes.io/aws-ebs` provisioner, which is not marked
default and — more importantly — no longer has a working controller behind it on current
Kubernetes versions (in-tree EBS support was removed after CSI migration completed). Installing
the `aws-ebs-csi-driver` addon does *not* automatically create a StorageClass either; you have to
apply one yourself, which is what `storageclass-gp3-csi.yaml` is for. This is why it's a required
step in [Spin up](#spin-up), not optional cleanup.

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
the namespace. `helm list -n castellan-test` will show it; `helm uninstall castellan -n
castellan-test` clears it before you can reinstall under the same name.

### Gotcha: stale `castellan-init` Job/PVC block a retry
`castellan-init` (`job-castellan-init.yaml`) and the PVC (`pvc-keri-data.yaml`) are both
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
  something to paper over by adding a destructive delete policy.

### Gotcha: init Job logs disappear on success
Because of the `hook-succeeded` delete policy above, `kubectl logs -l
app.kubernetes.io/component=castellan-init` will usually return nothing after a successful
`helm install` — the Job and its pod are already gone by the time the command returns. That's
expected, not a bug: `STATUS: deployed` from `helm install` is itself the proof it succeeded. If
you need to inspect a successful run's logs, temporarily remove `hook-succeeded` from the policy
in `job-castellan-init.yaml` before that one install.
