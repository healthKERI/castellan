# weirwood
Credential exchange server intended for use with the locksmith plugin, whisper. 

## Setup
Weirwood, in its current state, shares account resources with hkweb and is intended to be hosted via the nightingale 
repo:

to run weirwood, first source the hkweb venv via `source /path/to/nightingale/venv/hkweb/bin/activate`

Then navigate to the weirwood directory and run `pip install -e .`

Navigate back to nightingale root and source your nightingale venv

Next, run `source /path/to/nightingale/scripts/env.sh` to prepare the scripts' environment variables

Then run `./path/to/nightingale/scripts/local/create_keri_databases.sh`

Followed by `./path/to/nightingale/scripts/local/restart.sh` to start the services
