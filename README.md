# Castellan Credential Management Server
Credential exchange server intended for use with the locksmith castellan-plugin. 

## Setup

### Docker (recommended)
`docker compose up --build` starts everything castellan needs: MongoDB, the credential
server, the OOBI service, and the rack load balancer. See `docker/README.md` for details
on the services, ports, and volumes.

### Local development
Create a virtualenv and install castellan in editable mode:

```
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
```

A local MongoDB instance is required (`castellan up`/`castellan start` accept `--dbhost`/`--dbname`
to point at it). Run `pytest` to run the test suite.
