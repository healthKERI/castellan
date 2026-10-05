# -*- encoding: utf-8 -*-
"""
castellan.app.oobi_serving module

Falcon ASGI application for castellan's standalone OOBI service.

Usage:
    CLI:      castellan oobi start --host 0.0.0.0 --port 5924
    uvicorn:  uvicorn castellan.app.oobi_serving:app --host 0.0.0.0 --port 5924
"""

import os

import falcon.asgi
from hio.help import decking
from keri.app import habbing
from keri.core import routing, eventing, parsing
from keri.help import ogler
from keri.peer import exchanging
from keri.vdr import credentialing
from keri.vdr.eventing import Tevery

from castellan.app.api.oobi import OobiDispatchEnd, ServerOobiEnd, CastellanOobiEnd
from castellan.app.api.public_registrar import (
    RegistrarEnd,
    RegistrarTELEnd,
    RegistrarCredentialEnd,
    RegistrarCredentialSearchEnd,
    RegistrarOOBIEnd,
)
from castellan.core import httping
from castellan.core.basing import databaseInit
from castellan.core.services import MessageService, IdentifierService
from castellan.core.services.account_service import AccountService
from castellan.core.services.grant_service import GrantService
from castellan.core.services.issued_credential_service import IssuedCredentialService
from castellan.core.services.key_event_log_service import KeyEventLogService
from castellan.core.services.received_credential_service import (
    ReceivedCredentialService,
)
from castellan.core.services.registrar_service import RegistrarService
from castellan.core.services.schema_field_tracking_service import (
    SchemaFieldTrackingService,
)
from castellan.core.services.schema_service import SchemaService
from castellan.core.services.server_service import ServerService

logger = ogler.getLogger()


def create_app(
    dbhost: str | None = None,
    dbname: str | None = None,
    dbuser: str | None = None,
    dbpass: str | None = None,
) -> falcon.asgi.App:
    """
    Create and configure the Falcon ASGI application.

    Args:
        dbhost: MongoDB connection string (or CASTELLAN_DBHOST env var)
        dbname: MongoDB database name (or CASTELLAN_DBNAME env var)
        dbuser: MongoDB username (or CASTELLAN_DBUSER env var)
        dbpass: MongoDB password (or CASTELLAN_DBPASS env var)

    Returns:
        Configured Falcon ASGI application.
    """
    db_host = dbhost or os.getenv("CASTELLAN_DBHOST", "mongodb://localhost:27017")
    db_name = dbname or os.getenv("CASTELLAN_DBNAME", "castellan")
    db_user = dbuser or os.getenv("CASTELLAN_DBUSER")
    db_pass = dbpass or os.getenv("CASTELLAN_DBPASS")

    # Initialize KERI Habery
    hby = habbing.Habery(name="castellan_oobi", base="", temp=False)
    if (hab := hby.habByName("castellan_oobi")) is None:
        hab = hby.makeHab(name="castellan_oobi", transferable=False)

    cues = decking.Deck()
    rvy = routing.Revery(db=hby.db, cues=cues)

    rgy = credentialing.Regery(hby=hby, name="castellan_oobi", temp=False)

    # Create Tevery for TEL processing
    tvy = Tevery(reger=rgy.reger, db=hby.db, rvy=rvy, lax=True, local=False, cues=cues)

    databaseInit(host=db_host, name=db_name, username=db_user, password=db_pass)
    logger.info(f"Connected to MongoDB at {db_host}@{db_name}")

    exchanger = exchanging.Exchanger(hby=hby, handlers=[])

    rvy = routing.Revery(db=hby.db, cues=cues)
    kvy = eventing.Kevery(db=hby.db, lax=True, local=False, rvy=rvy, cues=cues)
    kvy.registerReplyRoutes(router=rvy.rtr)
    parser = parsing.Parser(
        framed=True,
        kvy=kvy,
        exc=exchanger,
        rvy=rvy,
    )

    account_svc = AccountService(
        kvy=kvy,
        parser=parser,
    )
    msg_svc = MessageService()
    kel_svc = KeyEventLogService(hby=hby)
    grant_svc = GrantService(hby=hby)
    field_tracking_svc = SchemaFieldTrackingService()
    issued_svc = IssuedCredentialService(
        hby=hby,
        rgy=rgy,
        tvy=tvy,
        parser=parser,
        kel_svc=kel_svc,
        field_tracking_svc=field_tracking_svc,
    )
    identifier_svc = IdentifierService(
        account_service=account_svc,
        issued_svc=issued_svc,
        kelSvc=kel_svc,
        grant_svc=grant_svc,
        parser=parser,
        kvy=kvy,
        tvy=tvy,
        hby=hby,
        castellan_hab=hab,
    )
    forward_handler = httping.ForwardHandler(
        hby=hby, message_service=msg_svc, identifier_service=identifier_svc
    )
    exchanger.addHandler(forward_handler)

    schema_svc = SchemaService(hby=hby)
    issued_svc = IssuedCredentialService(hby=hby, rgy=None, tvy=None, parser=parser)
    received_svc = ReceivedCredentialService(hby=hby, rgy=None, tvy=None, parser=parser)
    server_svc = ServerService(parser=None, kvy=None, kel_service=kel_svc)
    registrar_svc = RegistrarService(
        hby=hby,
        hab=hab,
        rgy=rgy,
        tvy=tvy,
        credential_service=issued_svc,
        key_event_log_service=kel_svc,
    )

    app = falcon.asgi.App(
        middleware=falcon.CORSMiddleware(allow_origins="*", allow_credentials="*")
    )

    httping.load_ends(
        app=app, identifier_service=identifier_svc, parser=server_svc.parser
    )
    app.add_route(
        "/oobi/{said}", OobiDispatchEnd(kel_svc, schema_svc, issued_svc, received_svc)
    )
    app.add_route("/oobi/server", ServerOobiEnd(server_svc, kel_svc))
    app.add_route("/oobi/castellan", CastellanOobiEnd(hab))

    app.add_route("/registrar", RegistrarEnd(registrar_svc))
    app.add_route("/registrar/tel", RegistrarTELEnd(registrar_svc))
    app.add_route("/registrar/credential/{said}", RegistrarCredentialEnd(registrar_svc))
    app.add_route(
        "/registrar/credentials/search", RegistrarCredentialSearchEnd(registrar_svc)
    )
    app.add_route("/registrar/oobi/{aid}", RegistrarOOBIEnd(registrar_svc))

    logger.info("Castellan OOBI ASGI app created")
    return app


# Module-level app for uvicorn import
app = create_app()
