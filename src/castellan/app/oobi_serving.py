# -*- encoding: utf-8 -*-
"""
castellan.app.oobi_serving module

Falcon application factory for castellan's standalone, unauthenticated OOBI
service. Streams already-signed CESR bytes and schema JSON straight out of
MongoDB — no KERI keystore/Habery, so it scales horizontally behind a load
balancer with zero shared keystore state.
"""

import falcon
from hio.core import http
from keri.app import indirecting
from keri.help import ogler

from castellan.app.api.oobi import CredentialOobiEnd, OobiDispatchEnd, ServerOobiEnd
from castellan.core.basing import databaseInit
from castellan.core.services.issued_credential_service import IssuedCredentialService
from castellan.core.services.key_event_log_service import KeyEventLogService
from castellan.core.services.received_credential_service import (
    ReceivedCredentialService,
)
from castellan.core.services.schema_service import SchemaService
from castellan.core.services.server_service import ServerService

logger = ogler.getLogger()


def setup(
    host="0.0.0.0",
    port=5924,
    dbhost=None,
    dbname=None,
    dbuser=None,
    dbpass=None,
):
    """
    Connect to MongoDB, wire the Falcon OOBI app, and return a list of hio
    doers ready for a Doist to run.

    Args:
        host:   HTTP server bind address (default 0.0.0.0).
        port:   HTTP server port (default 5924).
        dbhost: MongoDB connection string (default mongodb://localhost:27017).
        dbname: MongoDB database name (default castellan).
        dbuser: MongoDB username for authentication (optional).
        dbpass: MongoDB password for authentication (optional).

    Returns:
        List of hio Doers.
    """
    db_host = dbhost if dbhost else "mongodb://localhost:27017"
    db_name = dbname if dbname else "castellan"
    db_user = dbuser if dbuser else None
    db_pass = dbpass if dbpass else None

    databaseInit(host=db_host, name=db_name, username=db_user, password=db_pass)
    logger.info(f"Connected to MongoDB at {db_host}@{db_name}")

    kel_svc = KeyEventLogService(hby=None)
    schema_svc = SchemaService()
    issued_svc = IssuedCredentialService(hby=None, rgy=None, tvy=None, parser=None)
    received_svc = ReceivedCredentialService(hby=None, rgy=None, tvy=None, parser=None)
    server_svc = ServerService(parser=None, kvy=None, kel_service=kel_svc)

    app = falcon.App(
        middleware=falcon.CORSMiddleware(allow_origins="*", allow_credentials="*")
    )
    app.add_route("/oobi/{said}", OobiDispatchEnd(kel_svc, schema_svc))
    app.add_route(
        "/oobi/{said}/credential", CredentialOobiEnd(issued_svc, received_svc)
    )
    app.add_route("/oobi/server", ServerOobiEnd(server_svc, kel_svc))

    server = indirecting.createHttpServer(host=host, port=port, app=app)

    logger.info(f"Castellan OOBI service listening on {host}:{port}")
    return [http.ServerDoer(server=server)]
