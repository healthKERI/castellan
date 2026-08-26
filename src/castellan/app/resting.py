# -*- encoding: utf-8 -*-
"""
castellan.app.resting module

Falcon application factory and service wiring for the castellan credential server.
"""

import falcon
from castellan.app.api.identifier import (
    IdentifierCollectionEnd,
    IdentifierKelEnd,
    IdentifierResourceEnd,
)
from castellan.app.api.issued_credential import (
    IssuedCredentialCollectionEnd,
    IssuedCredentialResourceEnd,
)
from castellan.app.api.json_schema import (
    JsonSchemaCollectionEnd,
    JsonSchemaResourceEnd,
)
from castellan.app.api.message import MessageCollectionEnd, MessageResourceEnd
from castellan.app.api.schema_field_tracking import SchemaFieldTrackingEnd
from castellan.app.api.received_credential import (
    ReceivedCredentialCollectionEnd,
    ReceivedCredentialResourceEnd,
)
from castellan.app.api.registrar import (
    RegistrarOobiEnd,
    RegistrarTELEnd,
)
from hio.base import doing
from hio.core import http
from hio.help import decking
from keri import kering
from keri.app import indirecting, oobiing
from keri.core import eventing, parsing, routing
from keri.help import ogler
from keri.vdr import credentialing, verifying
from keri.vdr.eventing import Tevery

from castellan.core.authing import Authenticater, SignatureValidationComponent
from castellan.core.basing import databaseInit
from castellan.core.haberying import Hby
from castellan.core.services import (
    IssuedCredentialService,
    ReceivedCredentialService,
    MessageService,
    IdentifierService,
)

from castellan.core.services.account_service import AccountService
from castellan.core.services.key_event_log_service import KeyEventLogService
from castellan.core.services.registrar_service import RegistrarService
from castellan.core.services.schema_service import SchemaService
from castellan.core.services.schema_field_tracking_service import (
    SchemaFieldTrackingService,
)

logger = ogler.getLogger()


def setup(
    name="castellan",
    alias="castellan",
    base=None,
    bran=None,
    host="127.0.0.1",
    port=5923,
    dbhost=None,
    dbname=None,
    dbuser=None,
    dbpass=None,
):
    """
    Initialise all KERI components, connect to MongoDB, wire the Falcon app,
    and return a list of hio doers ready for directing.runController().

    Args:
        name:        KERI keystore name.
        alias:       KERI identifier alias.
        base:        Optional keystore path prefix.
        bran:        21-character keystore passcode.
        host:        HTTP server bind address (default 127.0.0.1).
        port:        HTTP server port (default 5923).
        dbhost:      MongoDB connection string (default mongodb://localhost:27017).
        dbname:      MongoDB database name (default healthKERI).
        dbuser:      MongoDB username for authentication (optional).
        dbpass:      MongoDB password for authentication (optional).

    Returns:
        List of hio Doers.
    """
    # ------------------------------------------------------------------ #
    # KERI components                                                 #
    # ------------------------------------------------------------------ #
    hby = Hby.hby(name=name, base=base, bran=bran)

    cues = decking.Deck()
    rvy = routing.Revery(db=hby.db, cues=cues)
    kvy = eventing.Kevery(db=hby.db, lax=True, local=False, rvy=rvy, cues=cues)
    kvy.registerReplyRoutes(router=rvy.rtr)

    rgy = credentialing.Regery(hby=hby, name=name, temp=False)
    verifier = verifying.Verifier(hby=hby, reger=rgy.reger)
    tvy = Tevery(
        reger=verifier.reger, db=hby.db, rvy=rvy, lax=True, local=False, cues=cues
    )
    parser = parsing.Parser(kvy=kvy, rvy=rvy, tvy=tvy, vry=verifier)

    hab = hby.habByName(alias)
    if hab is None:
        raise kering.ConfigurationError(f"Hab '{alias}' not found in keystore '{name}'")

    # ------------------------------------------------------------------ #
    # Configuration & database                                        #
    # ------------------------------------------------------------------ #
    db_host = dbhost if dbhost else "mongodb://mongodb:27017"
    db_name = dbname if dbname else "castellan"
    db_user = dbuser if dbuser else None
    db_pass = dbpass if dbpass else None

    databaseInit(host=db_host, name=db_name, username=db_user, password=db_pass)
    logger.info(f"Connected to MongoDB at {db_host}@{db_name}")

    # ------------------------------------------------------------------ #
    # Services                                                        #
    # ------------------------------------------------------------------ #
    account_svc = AccountService(
        kvy=kvy,
        parser=parser,
    )
    kel_svc = KeyEventLogService(hby=hby)
    schema_svc = SchemaService()
    field_tracking_svc = SchemaFieldTrackingService()
    issued_svc = IssuedCredentialService(
        hby=hby,
        rgy=rgy,
        tvy=tvy,
        parser=parser,
        kel_svc=kel_svc,
        field_tracking_svc=field_tracking_svc,
    )
    received_svc = ReceivedCredentialService(
        hby=hby,
        rgy=rgy,
        tvy=tvy,
        parser=parser,
        field_tracking_svc=field_tracking_svc,
    )

    msg_svc = MessageService()
    identifier_svc = IdentifierService(
        kelSvc=kel_svc, parser=parser, kvy=kvy, hby=hby, castellan_hab=hab
    )
    registrar_svc = RegistrarService(
        hby=hby,
        hab=hab,
        tvy=tvy,
        rgy=rgy,
        credential_service=issued_svc,
        key_event_log_service=kel_svc,
    )

    # ------------------------------------------------------------------ #
    # Falcon app                                                         #
    # ------------------------------------------------------------------ #
    app = falcon.App(
        middleware=falcon.CORSMiddleware(
            allow_origins="*",
            allow_credentials="*",
            expose_headers=[
                "cesr-attachment",
                "cesr-date",
                "content-type",
                "signature",
                "signature-input",
                "signify-resource",
                "signify-timestamp",
            ],
        )
    )

    # Existing credential routes
    app.add_route("/issued-credentials", IssuedCredentialCollectionEnd(issued_svc))
    app.add_route("/issued-credentials/{said}", IssuedCredentialResourceEnd(issued_svc))
    app.add_route(
        "/received-credentials", ReceivedCredentialCollectionEnd(received_svc)
    )
    app.add_route(
        "/received-credentials/{said}", ReceivedCredentialResourceEnd(received_svc)
    )

    # Registrar routes (TEL events + OOBI)
    app.add_route("/registrar/tel-events", RegistrarTELEnd(registrar_svc))

    # Standard KERI registrar OOBI (kering.Roles.registrar is the standard role name)
    app.add_route("/oobi/{cid}/registrar", RegistrarOobiEnd(hab))

    # Uploaded identifier routes
    app.add_route("/identifiers", IdentifierCollectionEnd(identifier_svc))
    app.add_route("/identifiers/{aid}", IdentifierResourceEnd(identifier_svc, kel_svc))
    app.add_route("/identifiers/{aid}/kel", IdentifierKelEnd(identifier_svc))

    # JSON Schema management routes
    app.add_route("/schemas", JsonSchemaCollectionEnd(schema_svc))
    app.add_route("/schemas/{said}", JsonSchemaResourceEnd(schema_svc))
    app.add_route("/schemas/{said}/fields", SchemaFieldTrackingEnd(field_tracking_svc))

    # Intra-enterprise mailbox routes
    app.add_route("/messages", MessageCollectionEnd(msg_svc))
    app.add_route("/messages/{id}", MessageResourceEnd(msg_svc))

    # Authentication middleware (reuses healthKERI account infrastructure)
    auth = Authenticater(hab, account_svc)
    app.add_middleware(
        SignatureValidationComponent(
            accountSvc=account_svc,
            hab=hab,
            parser=parser,
            auth=auth,
        )
    )

    # ------------------------------------------------------------------ #
    # 6. HTTP server doer                                                #
    # ------------------------------------------------------------------ #
    oobiery = oobiing.Oobiery(hby=hby)

    server = indirecting.createHttpServer(host=host, port=port, app=app)
    server_doer = http.ServerDoer(server=server)

    # Continuous escrow processing — runs every 0.5 s so out-of-order or
    # dependency-pending events are resolved without waiting for a new request.
    def _make_escrow_doer(process_fn, tock=0.5):
        def escrow_do(tymth, tock=tock, **kwa):
            yield tock
            while True:
                process_fn()
                yield tock

        return doing.doify(escrow_do)

    kvy_escrow_doer = _make_escrow_doer(kvy.processEscrows)
    tvy_escrow_doer = _make_escrow_doer(tvy.processEscrows)

    doers = [
        *oobiery.doers,
        server_doer,
        kvy_escrow_doer,
        tvy_escrow_doer,
    ]

    logger.info(f"Castellan credential server listening on {host}:{port}")
    return doers
