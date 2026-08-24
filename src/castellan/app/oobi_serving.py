# -*- encoding: utf-8 -*-
"""
castellan.app.oobi_serving module

Falcon application factory for castellan's standalone, unauthenticated OOBI
service. Streams already-signed CESR bytes and schema JSON straight out of
MongoDB — no KERI keystore/Habery, so it scales horizontally behind a load
balancer with zero shared keystore state.
"""

import falcon
from castellan.app.api.public_registrar import (
    RegistrarEnd,
    RegistrarTELEnd,
    RegistrarCredentialEnd,
    RegistrarCredentialSearchEnd,
    RegistrarOOBIEnd,
)
from castellan.core.services.registrar_service import RegistrarService
from hio.core import http
from hio.help import decking
from keri.app import indirecting, habbing
from keri.core import routing
from keri.help import ogler

from castellan.app.api.oobi import OobiDispatchEnd, ServerOobiEnd
from castellan.core.basing import databaseInit
from castellan.core.services.issued_credential_service import IssuedCredentialService
from castellan.core.services.key_event_log_service import KeyEventLogService
from castellan.core.services.received_credential_service import (
    ReceivedCredentialService,
)
from castellan.core.services.schema_service import SchemaService
from castellan.core.services.server_service import ServerService
from keri.vdr import credentialing
from keri.vdr.eventing import Tevery

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
    hby = habbing.Habery(name="castellan_oobi", base="", temp=False)
    if (hab := hby.habByName("castellan_oobi")) is None:
        hab = hby.makeHab(name="castellan_oobi", transferable=False)

    cues = decking.Deck()
    rvy = routing.Revery(db=hby.db, cues=cues)

    rgy = credentialing.Regery(hby=hby, name="castellan_oobi", temp=False)

    # Create Tevery for TEL processing
    tvy = Tevery(reger=rgy.reger, db=hby.db, rvy=rvy, lax=True, local=False, cues=cues)

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
    registrar_svc = RegistrarService(
        hby=hby,
        hab=hab,
        rgy=rgy,
        tvy=tvy,
        credential_service=issued_svc,
        key_event_log_service=kel_svc,
    )

    app = falcon.App(
        middleware=falcon.CORSMiddleware(allow_origins="*", allow_credentials="*")
    )
    app.add_route(
        "/oobi/{said}", OobiDispatchEnd(kel_svc, schema_svc, issued_svc, received_svc)
    )
    app.add_route("/oobi/server", ServerOobiEnd(server_svc, kel_svc))

    app.add_route("/registrar", RegistrarEnd(registrar_svc))
    app.add_route("/registrar/tel", RegistrarTELEnd(registrar_svc))
    app.add_route("/registrar/credential/{said}", RegistrarCredentialEnd(registrar_svc))
    app.add_route(
        "/registrar/credentials/search", RegistrarCredentialSearchEnd(registrar_svc)
    )
    app.add_route("/registrar/oobi/{aid}", RegistrarOOBIEnd(registrar_svc))

    server = indirecting.createHttpServer(host=host, port=port, app=app)

    logger.info(f"Castellan OOBI service listening on {host}:{port}")
    return [http.ServerDoer(server=server)]
