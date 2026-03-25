# -*- encoding: utf-8 -*-
"""
weirwood.app.resting module

Falcon application factory and service wiring for the weirwood credential server.
"""
import os

import falcon
from hio.core import http
from hio.help import decking
from hksvc.core import (AccountService, TeamService, Authenticater,
                         SignatureValidationComponent, VMService,
                         KeyEventLogService)
from hksvc.core.basing import databaseInit
from hksvc.core.haberying import Hby
from keri import kering
from keri.app import configing, indirecting, oobiing
from keri.core import eventing, parsing, routing
from keri.help import ogler
from keri.vdr import credentialing, verifying
from keri.vdr.eventing import Tevery

from weirwood.app.api.issued_credential import (
    IssuedCredentialCollectionEnd, IssuedCredentialResourceEnd
)
from weirwood.app.api.received_credential import (
    ReceivedCredentialCollectionEnd, ReceivedCredentialResourceEnd
)
from weirwood.core.services import IssuedCredentialService, ReceivedCredentialService

logger = ogler.getLogger()


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
    # 1. KERI components                                                   #
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

    # ------------------------------------------------------------------ #
    # 2. Configuration & database                                          #
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
    # 3. Services                                                          #
    # ------------------------------------------------------------------ #
    vmSvc = VMService()
    accountSvc = AccountService(kvy=kvy, parser=parser, vm_svc=vmSvc)
    kelSvc = KeyEventLogService(hby=hby)
    teamSvc = TeamService(accountSvc=accountSvc, kelSvc=kelSvc)
    issuedSvc = IssuedCredentialService(hby=hby, rgy=rgy, tvy=tvy, parser=parser)
    receivedSvc = ReceivedCredentialService(hby=hby, rgy=rgy, tvy=tvy, parser=parser)

    # ------------------------------------------------------------------ #
    # 4. Falcon app                                                        #
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

    # Routes
    app.add_route("/issued-credentials",
                  IssuedCredentialCollectionEnd(issuedSvc))
    app.add_route("/issued-credentials/{said}",
                  IssuedCredentialResourceEnd(issuedSvc))
    app.add_route("/received-credentials",
                  ReceivedCredentialCollectionEnd(receivedSvc))
    app.add_route("/received-credentials/{said}",
                  ReceivedCredentialResourceEnd(receivedSvc))

    # Authentication middleware (reuses healthKERI account infrastructure)
    auth = Authenticater(hab, accountSvc)
    app.add_middleware(SignatureValidationComponent(
        accountSvc=accountSvc, teamSvc=teamSvc,
        hab=hab, parser=parser, auth=auth,
    ))

    # ------------------------------------------------------------------ #
    # 5. HTTP server doer                                                  #
    # ------------------------------------------------------------------ #
    oobiery = oobiing.Oobiery(hby=hby)

    server = indirecting.createHttpServer(
        host=host, port=port, app=app,
        keypath=keypath, certpath=certpath, cafilepath=cafilepath,
    )
    serverDoer = http.ServerDoer(server=server)

    doers = [*oobiery.doers, serverDoer]

    logger.info(f"Weirwood credential server listening on {host}:{port}")
    return doers