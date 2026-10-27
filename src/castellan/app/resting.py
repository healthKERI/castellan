# -*- encoding: utf-8 -*-
"""
castellan.app.resting module

Falcon ASGI application factory and service wiring for the castellan credential server.
"""

import os

import falcon.asgi
from keri import kering
from keri.core import eventing, parsing, routing
from keri.help import ogler
from keri.peer import exchanging
from keri.vdr import credentialing, verifying
from keri.vdr.eventing import Tevery

from castellan.app.api.account import AccountCollectionEnd, AccountResourceEnd
from castellan.app.api.health import HealthEnd
from castellan.app.api.identifier import (
    IdentifierCollectionEnd,
    IdentifierKelEnd,
    IdentifierResourceEnd,
    MultisigIdentifierCollectionEnd,
    MultisigIdentifierResourceEnd,
    MultisigIdentifierSignatureCollectionEnd,
    MultisigIdentifierRegistryCollectionEnd,
    MultisigIdentifierWitnessCollectionEnd,
    MultisigIdentifierWitnessResourceEnd,
    MultisigIdentifierCredentialCollectionEnd,
    MultisigRegsitrySignatureCollectionEnd,
)
from castellan.app.api.issued_credential import (
    IssuedCredentialCollectionEnd,
    IssuedCredentialResourceEnd,
)
from castellan.app.api.json_schema import (
    JSONSchemaCollectionEnd,
    JsonSchemaResourceEnd,
)
from castellan.app.api.message import MessageCollectionEnd, MessageResourceEnd
from castellan.app.api.received_credential import (
    ReceivedCredentialCollectionEnd,
    ReceivedCredentialResourceEnd,
)
from castellan.app.api.registrar import (
    RegistrarOobiEnd,
    RegistrarTELEnd,
)
from castellan.app.api.schema_field_tracking import SchemaFieldTrackingEnd
from castellan.app.tasking import CastellanBackgroundWorker, LifespanMiddleware
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
from castellan.core.services.grant_service import GrantService
from castellan.core.services.key_event_log_service import KeyEventLogService
from castellan.core.services.registrar_service import RegistrarService
from castellan.core.services.schema_field_tracking_service import (
    SchemaFieldTrackingService,
)
from castellan.core.services.schema_service import SchemaService

logger = ogler.getLogger()


def create_app(
    name=None,
    alias=None,
    base=None,
    bran=None,
    dbhost=None,
    dbname=None,
    dbuser=None,
    dbpass=None,
):
    """
    Initialise all KERI components, connect to MongoDB, wire the Falcon ASGI app,
    and return the app along with background task factories.

    Args:
        name:        KERI keystore name (or from env CASTELLAN_NAME).
        alias:       KERI identifier alias (or from env CASTELLAN_ALIAS).
        base:        Optional keystore path prefix (or from env CASTELLAN_BASE).
        bran:        21-character keystore passcode (or from env CASTELLAN_BRAN).
        dbhost:      MongoDB connection string (or from env CASTELLAN_DBHOST).
        dbname:      MongoDB database name (or from env CASTELLAN_DBNAME).
        dbuser:      MongoDB username (or from env CASTELLAN_DBUSER).
        dbpass:      MongoDB password (or from env CASTELLAN_DBPASS).

    Returns:
        Tuple of (falcon.asgi.App, list of background task factories).
    """
    # Read from environment if not provided
    name = name or os.environ.get("CASTELLAN_NAME", "castellan")
    alias = alias or os.environ.get("CASTELLAN_ALIAS", "castellan")
    base = base or os.environ.get("CASTELLAN_BASE") or ""
    bran = bran or os.environ.get("CASTELLAN_BRAN") or None
    dbhost = dbhost or os.environ.get("CASTELLAN_DBHOST")
    dbname = dbname or os.environ.get("CASTELLAN_DBNAME")
    dbuser = dbuser or os.environ.get("CASTELLAN_DBUSER")
    dbpass = dbpass or os.environ.get("CASTELLAN_DBPASS")

    # ------------------------------------------------------------------ #
    # KERI components                                                    #
    # ------------------------------------------------------------------ #
    hby = Hby.hby(name=name, base=base, bran=bran)

    rvy = routing.Revery(db=hby.db)
    kvy = eventing.Kevery(db=hby.db, lax=True, local=True, rvy=rvy)
    kvy.registerReplyRoutes(router=rvy.rtr)

    rgy = credentialing.Regery(hby=hby, name=name, temp=False)
    verifier = verifying.Verifier(hby=hby, reger=rgy.reger)
    tvy = Tevery(reger=verifier.reger, db=hby.db, rvy=rvy, lax=True, local=True)
    exc = exchanging.Exchanger(hby=hby, handlers=[])
    parser = parsing.Parser(kvy=kvy, rvy=rvy, tvy=tvy, vry=verifier, exc=exc)

    hab = hby.habByName(alias)
    if hab is None:
        raise kering.ConfigurationError(f"Hab '{alias}' not found in keystore '{name}'")

    # ------------------------------------------------------------------ #
    # Configuration & database                                           #
    # ------------------------------------------------------------------ #
    db_host = dbhost if dbhost else "mongodb://mongodb:27017"
    db_name = dbname if dbname else "castellan"
    db_user = dbuser if dbuser else None
    db_pass = dbpass if dbpass else None

    databaseInit(host=db_host, name=db_name, username=db_user, password=db_pass)
    logger.info(f"Connected to MongoDB at {db_host}@{db_name}")

    # ------------------------------------------------------------------ #
    # Services                                                           #
    # ------------------------------------------------------------------ #
    account_svc = AccountService(
        kvy=kvy,
        parser=parser,
    )
    kel_svc = KeyEventLogService(hby=hby)
    schema_svc = SchemaService(hby=hby)
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
    received_svc = ReceivedCredentialService(
        hby=hby,
        rgy=rgy,
        tvy=tvy,
        parser=parser,
        field_tracking_svc=field_tracking_svc,
    )

    msg_svc = MessageService()
    identifier_svc = IdentifierService(
        account_service=account_svc,
        issued_svc=issued_svc,
        kelSvc=kel_svc,
        grant_svc=grant_svc,
        parser=parser,
        kvy=kvy,
        tvy=tvy,
        verifier=verifier,
        hby=hby,
        rgy=rgy,
        castellan_hab=hab,
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
    # Falcon ASGI app                                                    #
    # ------------------------------------------------------------------ #
    falcon_app = falcon.asgi.App(
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
    falcon_app.add_route(
        "/issued-credentials", IssuedCredentialCollectionEnd(issued_svc)
    )
    falcon_app.add_route(
        "/issued-credentials/{said}", IssuedCredentialResourceEnd(issued_svc)
    )
    falcon_app.add_route(
        "/received-credentials", ReceivedCredentialCollectionEnd(received_svc)
    )
    falcon_app.add_route(
        "/received-credentials/{said}", ReceivedCredentialResourceEnd(received_svc)
    )

    # Registrar routes (TEL events + OOBI)
    falcon_app.add_route("/registrar/tel-events", RegistrarTELEnd(registrar_svc))

    # Standard KERI registrar OOBI (kering.Roles.registrar is the standard role name)
    falcon_app.add_route("/oobi/{cid}/registrar", RegistrarOobiEnd(hab))

    # Uploaded identifier routes
    falcon_app.add_route("/identifiers", IdentifierCollectionEnd(identifier_svc))
    falcon_app.add_route(
        "/identifiers/{aid}", IdentifierResourceEnd(identifier_svc, kel_svc)
    )
    falcon_app.add_route("/identifiers/{aid}/kel", IdentifierKelEnd(identifier_svc))

    falcon_app.add_route(
        "/multisig/identifiers", MultisigIdentifierCollectionEnd(identifier_svc)
    )
    falcon_app.add_route(
        "/multisig/identifiers/{multisig_id}",
        MultisigIdentifierResourceEnd(identifier_svc),
    )
    falcon_app.add_route(
        "/multisig/identifiers/{multisig_id}/signatures",
        MultisigIdentifierSignatureCollectionEnd(identifier_svc),
    )
    falcon_app.add_route(
        "/multisig/identifiers/{multisig_id}/registries",
        MultisigIdentifierRegistryCollectionEnd(identifier_svc),
    )
    falcon_app.add_route(
        "/multisig/identifiers/{multisig_id}/registries/signatures",
        MultisigRegsitrySignatureCollectionEnd(identifier_svc),
    )
    falcon_app.add_route(
        "/multisig/identifiers/{multisig_id}/credentials",
        MultisigIdentifierCredentialCollectionEnd(identifier_svc),
    )
    falcon_app.add_route(
        "/multisig/identifiers/{multisig_id}/witnesses",
        MultisigIdentifierWitnessCollectionEnd(identifier_svc),
    )
    falcon_app.add_route(
        "/multisig/identifiers/{multisig_id}/witnesses/rotate",
        MultisigIdentifierWitnessResourceEnd(identifier_svc),
    )

    # JSON Schema management routes
    falcon_app.add_route("/schemas", JSONSchemaCollectionEnd(schema_svc))
    falcon_app.add_route("/schemas/{said}", JsonSchemaResourceEnd(schema_svc))
    falcon_app.add_route(
        "/schemas/{said}/fields", SchemaFieldTrackingEnd(field_tracking_svc)
    )

    # Intra-enterprise mailbox routes
    falcon_app.add_route("/messages", MessageCollectionEnd(msg_svc))
    falcon_app.add_route("/messages/{id}", MessageResourceEnd(msg_svc))

    # Account management routes
    falcon_app.add_route("/accounts", AccountCollectionEnd(account_svc))
    falcon_app.add_route("/accounts/{aid}", AccountResourceEnd(account_svc))

    # Health check route (authenticated - verifies the signed connection works
    # end-to-end, not just that the process is alive)
    falcon_app.add_route("/health", HealthEnd())

    # Authentication middleware (reuses healthKERI account infrastructure)
    auth = Authenticater(hab, account_svc)
    falcon_app.add_middleware(
        SignatureValidationComponent(
            accountSvc=account_svc,
            hab=hab,
            parser=parser,
            auth=auth,
        )
    )

    # ------------------------------------------------------------------ #
    # Background task factories                                          #
    # ------------------------------------------------------------------ #
    worker = CastellanBackgroundWorker(hby=hby, kvy=kvy, tvy=tvy, rvy=rvy)
    falcon_app.add_middleware(LifespanMiddleware(worker))

    logger.info("Castellan ASGI app created")
    return falcon_app


# Module-level app for uvicorn
app = create_app()
