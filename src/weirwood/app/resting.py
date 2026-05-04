# -*- encoding: utf-8 -*-
"""
weirwood.app.resting module

Falcon application factory and service wiring for the weirwood credential server.
"""
import base64
import os

import falcon
from hio.base import doing
from hio.core import http
from hio.help import decking
from hksvc.core import (AccountService, TeamService, Authenticater,
                         SignatureValidationComponent, VMService,
                         KeyEventLogService)
from hksvc.core.basing import databaseInit
from hksvc.core.haberying import Hby
from keri import kering
from keri.app import configing, indirecting, oobiing
from keri.app import habbing
from keri.peer import exchanging
from keri.core import eventing, parsing, routing
from keri.help import ogler
from keri.vdr import credentialing, verifying
from keri.vdr.eventing import Tevery

from weirwood.app.api.identifier import IdentifierCollectionEnd, IdentifierKelEnd, IdentifierResourceEnd
from weirwood.app.api.issued_credential import (
    IssuedCredentialCollectionEnd, IssuedCredentialResourceEnd
)
from weirwood.app.api.received_credential import (
    ReceivedCredentialCollectionEnd, ReceivedCredentialResourceEnd
)
from weirwood.app.api.registrar import (
    RegistrarTelCollectionEnd, RegistrarTelResourceEnd, RegistrarOobiEnd,
    RegistrarBackerEnd, MailboxOobiEnd,
)
from weirwood.app.api.message import MessageCollectionEnd, MessageResourceEnd
from weirwood.core.services import (
    IssuedCredentialService, ReceivedCredentialService,
    TelEventService, MessageService, IdentifierService,
)
from weirwood.app.api.cesr_inbound import (
    CesrInboundEnd, WeirwoodForwardHandler, WeirwoodIpexGrantHandler, QviAdmitDoer,
)

logger = ogler.getLogger()
WEIRWOOD_CESR_PORT = 5925

def _register_registrar_endpoint(hab, parser, host, port):
    """
    Register weirwood's HTTP location and registrar end-role in its KERI database
    so that hab.replyToOobi(role='registrar') can serve a valid OOBI reply.

    Writes signed /loc/scheme and /end/role/add reply events into the hab's
    LMDB via the supplied parser/rvy.  Idempotent — safe to call on every
    startup; existing entries are overwritten with fresh timestamps.
    """
    try:
        scheme = kering.Schemes.http
        url = f"http://{host}:{port}"

        # Build signed reply events (bytearray streams)
        loc_msgs = hab.makeLocScheme(url=url, scheme=scheme)
        role_msgs = hab.makeEndRole(eid=hab.pre, role=kering.Roles.registrar)

        # Process each event stream in-place to persist to LMDB
        for msgs in (loc_msgs, role_msgs):
            if msgs:
                ims = bytearray(msgs)
                parser.parse(ims=ims)

        logger.info(
            f"Registered weirwood registrar endpoint: {url} "
            f"(eid={hab.pre}, role={kering.Roles.registrar})"
        )
    except Exception as e:
        logger.warning(
            f"Could not register registrar OOBI endpoint: {e}. "
            "The /oobi/{{cid}}/registrar route will return 404 until resolved."
        )


def setup(name="weirwood", alias="weirwood", base=None, bran=None,
          headDirPath=None, host="127.0.0.1", port=5923,
          keypath=None, certpath=None, cafilepath=None):
    """
    Initialise all KERI components, connect to MongoDB, wire the Falcon app,
    and return a list of hio doers ready for directing.runController().

    Args:
        name:        KERI keystore name.
        alias:       KERI identifier alias.
        base:        Optional keystore path prefix.
        bran:        21-character keystore passcode.
        headDirPath: Config directory override.
        host:        HTTP server bind address (default 127.0.0.1).
        port:        HTTP server port (default 5923).
        keypath:     TLS key path (optional).
        certpath:    TLS cert path (optional).
        cafilepath:  TLS CA file path (optional).

    Returns:
        List of hio Doers.
    """
    # ------------------------------------------------------------------ #
    # 1. KERI components                                                 #
    # ------------------------------------------------------------------ #
    hby = Hby.hby(name=name, base=base, bran=bran)

    cues = decking.Deck()
    rvy = routing.Revery(db=hby.db, cues=cues)
    kvy = eventing.Kevery(db=hby.db, lax=True, local=False, rvy=rvy, cues=cues)
    kvy.registerReplyRoutes(router=rvy.rtr)

    rgy = credentialing.Regery(hby=hby, name=name, temp=False)
    verifier = verifying.Verifier(hby=hby, reger=rgy.reger)
    tvy = Tevery(reger=verifier.reger, db=hby.db, rvy=rvy,
                 lax=True, local=False, cues=cues)
    parser = parsing.Parser(kvy=kvy, rvy=rvy, tvy=tvy, vry=verifier)

    hab = hby.habByName(alias)
    if hab is None:
        raise kering.ConfigurationError(f"Hab '{alias}' not found in keystore '{name}'")

    # Non-transferable identifier used as TEL registry backer.
    # Must be non-transferable so its signing key (= its prefix) is permanently stable.
    backer_alias = f"{alias}-backer"
    backer_hab = hby.habByName(backer_alias)
    if backer_hab is None:
        backer_hab = hby.makeHab(name=backer_alias, transferable=False)
        logger.info(f"Created non-transferable backer identifier: {backer_hab.pre}")

    # ------------------------------------------------------------------ #
    # 2. Configuration & database                                        #
    # ------------------------------------------------------------------ #
    cf = configing.Configer(name=name, headDirPath=headDirPath)
    conf = cf.get()
    conf = conf.get("weirwood", conf.get("hkapi", {}))

    dbHost = conf.get("host", "mongodb://localhost:27017")
    dbName = conf.get("name", "healthKERI")
    dbUser = conf.get("username", None)
    dbPass = conf.get("password", None)

    databaseInit(host=dbHost, name=dbName, username=dbUser, password=dbPass)
    logger.info(f"Connected to MongoDB at {dbHost}@{dbName}")

    # ------------------------------------------------------------------ #
    # 3. Register weirwood as registrar endpoint (for OOBI resolution)   #
    # ------------------------------------------------------------------ #
    _register_registrar_endpoint(hab, parser, host, port)


    # ------------------------------------------------------------------ #
    # 4. Services                                                        #
    # ------------------------------------------------------------------ #
    vmSvc = VMService()
    accountSvc = AccountService(kvy=kvy, parser=parser, vm_svc=vmSvc)
    kelSvc = KeyEventLogService(hby=hby)
    teamSvc = TeamService(accountSvc=accountSvc, kelSvc=kelSvc)
    issuedSvc = IssuedCredentialService(hby=hby, rgy=rgy, tvy=tvy, parser=parser)
    receivedSvc = ReceivedCredentialService(hby=hby, rgy=rgy, tvy=tvy, parser=parser)
    telSvc = TelEventService(hby=hby, tvy=tvy, parser=parser, hab=backer_hab)
    msgSvc = MessageService()
    identifierSvc = IdentifierService(kelSvc=kelSvc, parser=parser, kvy=kvy, hby=hby, weirwood_hab=hab)
    admit_cues = decking.Deck()

    # ------------------------------------------------------------------ #
    # 5. Falcon app                                                      #
    # ------------------------------------------------------------------ #
    app = falcon.App(middleware=falcon.CORSMiddleware(
        allow_origins="*",
        allow_credentials="*",
        expose_headers=[
            "cesr-attachment", "cesr-date", "content-type",
            "signature", "signature-input",
            "signify-resource", "signify-timestamp",
        ],
    ))

    # Existing credential routes
    app.add_route("/issued-credentials",
                  IssuedCredentialCollectionEnd(issuedSvc))
    app.add_route("/issued-credentials/{said}",
                  IssuedCredentialResourceEnd(issuedSvc))
    app.add_route("/received-credentials",
                  ReceivedCredentialCollectionEnd(receivedSvc))
    app.add_route("/received-credentials/{said}",
                  ReceivedCredentialResourceEnd(receivedSvc))

    # Registrar routes (TEL events + OOBI)
    app.add_route("/registrar/tel-events",
                  RegistrarTelCollectionEnd(telSvc))
    app.add_route("/registrar/tel-events/{regk}",
                  RegistrarTelResourceEnd(telSvc))
    app.add_route("/registrar/tel-events/{regk}/{vcid}",
                  RegistrarTelResourceEnd(telSvc))
    # Standard KERI registrar OOBI (kering.Roles.registrar is the standard role name)
    app.add_route("/oobi/{cid}/registrar",
                  RegistrarOobiEnd(hab))
    # Non-transferable backer identifier AID + KEL for whisper instances to fetch
    app.add_route("/registrar/backer",
                  RegistrarBackerEnd(hby=hby, hab=backer_hab))

    # Uploaded identifier routes
    app.add_route("/identifiers",
                  IdentifierCollectionEnd(identifierSvc))
    app.add_route("/identifiers/{aid}",
                  IdentifierResourceEnd(identifierSvc))
    app.add_route("/identifiers/{aid}/kel",
                  IdentifierKelEnd(identifierSvc))

    # Intra-enterprise mailbox routes
    app.add_route("/messages",
                  MessageCollectionEnd(msgSvc))
    app.add_route("/messages/{id}",
                  MessageResourceEnd(msgSvc))

    # Authentication middleware (reuses healthKERI account infrastructure)
    auth = Authenticater(hab, accountSvc)
    app.add_middleware(SignatureValidationComponent(
        accountSvc=accountSvc, teamSvc=teamSvc,
        hab=hab, parser=parser, auth=auth,
    ))

    # CESR ingestion — build Exchanger before constructing the endpoint
    fwd_handler = WeirwoodForwardHandler(hby=hby, message_service=msgSvc)
    ipex_handler = WeirwoodIpexGrantHandler(
        hby=hby,
        hab=hab,
        rgy=rgy,
        verifier=verifier,
        tvy=tvy,
        received_svc=receivedSvc,
        admit_cues=admit_cues,
    )
    exc = exchanging.Exchanger(hby=hby, handlers=[fwd_handler, ipex_handler])

    # Break circular dependency: fwd_handler needs parser+exc to re-dispatch
    # inner IPEX embeds, but exc needs fwd_handler at construction time.
    fwd_handler.parser = parser
    fwd_handler.exc = exc

    admit_doer = QviAdmitDoer(hby=hby, hab=hab, admit_cues=admit_cues, exc=exc)

    cesr_end = CesrInboundEnd(exc=exc, kvy=kvy, rvy=rvy, tvy=tvy)
    cesr_app = falcon.App()

    cesr_app.add_route("/", cesr_end)
    cesr_app.add_route("/oobi/{cid}/mailbox/{eid}", MailboxOobiEnd(hab))
    cesr_server = indirecting.createHttpServer(
        host="127.0.0.1",   # 0.0.0.0 in production
        port=WEIRWOOD_CESR_PORT,
        app=cesr_app,
    )
    cesr_server_doer = http.ServerDoer(server=cesr_server)

    # Register weirwood's CESR endpoint as its mailbox location
    cesr_url = f"http://127.0.0.1:{WEIRWOOD_CESR_PORT}"
    loc_msgs = hab.makeLocScheme(url=cesr_url, scheme=kering.Schemes.http)
    parser.parse(ims=bytearray(loc_msgs))

    mailbox_role_msgs = hab.makeEndRole(eid=hab.pre, role=kering.Roles.mailbox)
    parser.parse(ims=bytearray(mailbox_role_msgs))

    # Dev startup: register weirwood as mailbox for all group HABs already in keystore
    for pre, group_hab in hby.habs.items():
        if isinstance(group_hab, habbing.GroupHab):
            role_msgs = group_hab.makeEndRole(eid=hab.pre, role=kering.Roles.mailbox)
            parser.parse(ims=bytearray(role_msgs))

    # ------------------------------------------------------------------ #
    # 6. HTTP server doer                                                #
    # ------------------------------------------------------------------ #
    oobiery = oobiing.Oobiery(hby=hby)

    server = indirecting.createHttpServer(
        host=host, port=port, app=app,
        keypath=keypath, certpath=certpath, cafilepath=cafilepath,
    )
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

    doers = [*oobiery.doers, server_doer, cesr_server_doer, kvy_escrow_doer, tvy_escrow_doer, admit_doer]

    logger.info(f"Weirwood credential server listening on {host}:{port}")
    return doers