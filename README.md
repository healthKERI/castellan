# Castellan Credential Management Server
Credential exchange server intended for use with the locksmith castellan-plugin. 

## Setup

### Docker (recommended)
`docker compose up --build` starts everything castellan needs: MongoDB, the credential
server, the OOBI service, and the rack load balancer. See `docker/README.md` for details
on the services, ports, and volumes.

### Kubernetes
`charts/castellan` is a Helm chart for deploying to Kubernetes (MongoDB hosted externally).
See `charts/castellan/values.yaml` for configuration and `helm template charts/castellan` to
render manifests. See `charts/castellan/testing/README.md` for a full walkthrough of standing up
a disposable EKS cluster to test the chart end to end.

### Local development
Create a virtualenv and install castellan in editable mode:

```
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
```

A local MongoDB instance is required (`castellan up`/`castellan start` accept `--dbhost`/`--dbname`
to point at it). Run `pytest` to run the test suite.
