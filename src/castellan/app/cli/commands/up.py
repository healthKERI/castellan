# -*- encoding: utf-8 -*-
import argparse

from castellan.core.basing import databaseInit
from castellan.core.services.key_event_log_service import KeyEventLogService
from castellan.core.services.server_service import ServerService
from keri import help
from keri.app import habbing
from keri.app.keeping import Algos
from keri.core.parsing import Parser
from keri.kering import Schemes, Roles

parser = argparse.ArgumentParser(
    description="New access code(s) to the system for new account creation"
)
parser.set_defaults(handler=lambda args: create(args))
parser.add_argument(
    "--name", "-n", help="KERI keystore name and file location", required=True
)
parser.add_argument(
    "--alias", "-a", help="Human-readable alias for the identifier", required=True
)
parser.add_argument(
    "--passcode",
    "-p",
    dest="bran",
    default=None,
    help="21-character encryption passcode for the keystore (not saved).",
)
parser.add_argument(
    "--base",
    "-b",
    help="Optional prefix for the KERI keystore file location",
    required=False,
    default="",
)
parser.add_argument(
    "--salt",
    "-s",
    help="qualified base64 salt for creating key pairs",
    required=False,
    default=None,
)
parser.add_argument(
    "--ipaddress",
    "-I",
    action="store",
    default="127.0.0.1",
    help="HTTP server bind address (default 127.0.0.1).",
)
parser.add_argument(
    "--port",
    "-P",
    action="store",
    type=int,
    default=5923,
    help="HTTP server port (default 5923).",
)
parser.add_argument("--dbhost", action="store", required=False, default=None)
parser.add_argument("--dbname", action="store", required=False, default=None)
parser.add_argument("--dbuser", action="store", required=False, default=None)
parser.add_argument("--dbpass", action="store", required=False, default=None)


def create(args):
    kwa = dict()
    kwa["salt"] = args.salt
    kwa["bran"] = args.bran
    if args.salt is None:
        kwa["algo"] = Algos.randy

    # Create environment and identifier for the ACDC Auth Server
    hby = habbing.Habery(name=args.name, base=args.base, temp=False, **kwa)
    if not (hab := hby.habByName(args.alias)):
        hab = hby.makeHab(
            name=args.alias,
            transferable=True,
            icount=1,
            isith="1",
            ncount=1,
            nsith="1",
            toad=0,
        )

    msg = hab.makeEndRole(eid=hab.pre, role=Roles.controller, stamp=help.nowIso8601())
    Parser().parse(ims=bytes(msg), kvy=hab.kvy, rvy=hab.rvy)

    url = f"tcp://{args.ipaddress}:{args.port}"
    msg = hab.makeLocScheme(url=url, eid=hab.pre, scheme=Schemes.tcp)
    Parser().parse(ims=bytes(msg), kvy=hab.kvy, rvy=hab.rvy)

    db_host = args.dbhost if args.dbhost else "mongodb://localhost:27017"
    db_name = args.dbname if args.dbname else "castellan"
    db_user = args.dbuser if args.dbuser else None
    db_pass = args.dbpass if args.dbpass else None

    databaseInit(host=db_host, name=db_name, username=db_user, password=db_pass)
    key_service = KeyEventLogService(hby=hby)
    server_service = ServerService(parser=hab.psr, kvy=hab.kvy, kel_service=key_service)

    doc = dict(aid=hab.pre, ipaddress=args.ipaddress, port=int(args.port))
    kel = hab.replyToOobi(aid=hab.pre, role="controller")

    print(kel)
    server_service.create_server(doc, kel)

    print(
        f"Server created successfully for {hab.name} with AID {hab.pre} as {args.ipaddress}:{args.port}"
    )
