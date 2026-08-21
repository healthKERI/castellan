# -*- encoding: utf-8 -*-
import argparse
from urllib.parse import urlparse

from castellan.core.basing import databaseInit
from castellan.core.services.key_event_log_service import KeyEventLogService
from castellan.core.services.server_service import ServerService
from keri.app.cli.common import existing
from keri.kering import Schemes

parser = argparse.ArgumentParser(
    description="New access code(s) to the system for new account creation"
)
parser.set_defaults(handler=lambda args: up(args))
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
parser.add_argument("--dbhost", action="store", required=False, default=None)
parser.add_argument("--dbname", action="store", required=False, default=None)
parser.add_argument("--dbuser", action="store", required=False, default=None)
parser.add_argument("--dbpass", action="store", required=False, default=None)


def up(args):
    with existing.existingHab(args.name, args.alias, args.base, args.bran) as (
        hby,
        hab,
    ):
        urls = hab.fetchUrls(eid=hab.pre, scheme=Schemes.tcp)
        if not urls:
            raise ValueError("No TCP URL found for castellan")
        tcp_url = urls.get(Schemes.tcp, None)
        up = urlparse(tcp_url)
        ipaddress = up.hostname
        port = up.port

        db_host = args.dbhost if args.dbhost else "mongodb://localhost:27017"
        db_name = args.dbname if args.dbname else "castellan"
        db_user = args.dbuser if args.dbuser else None
        db_pass = args.dbpass if args.dbpass else None

        databaseInit(host=db_host, name=db_name, username=db_user, password=db_pass)
        key_service = KeyEventLogService(hby=hby)
        server_service = ServerService(
            parser=hab.psr, kvy=hab.kvy, kel_service=key_service
        )

        if server_service.server_exists(hab.pre):
            print(
                f"Server already registered for {hab.name} with AID {hab.pre}; skipping."
            )
            return

        doc = dict(aid=hab.pre, ipaddress=ipaddress, port=int(port))
        kel = hab.replyToOobi(aid=hab.pre, role="controller")

        server_service.create_server(doc, kel)

        print(
            f"Server created successfully for {hab.name} with AID {hab.pre} as {ipaddress}:{port}"
        )
