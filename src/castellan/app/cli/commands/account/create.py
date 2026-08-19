# -*- encoding: utf-8 -*-
import argparse
import re
from urllib import parse

import requests
from keri.app.cli.common import existing
from keri.kering import ConfigurationError

from castellan.core.basing import databaseInit
from castellan.core.services.account_service import AccountService

parser = argparse.ArgumentParser(description="New access code(s) to the system for new account creation")
parser.set_defaults(handler=lambda args: create(args))
parser.add_argument("--name", "-n",
                    help="KERI keystore name and file location",
                    required=True)
parser.add_argument("--alias", "-a",
                    help="Human-readable alias for the identifier",
                    required=True)
parser.add_argument("--passcode", "-p",
                    dest="bran",
                    default=None,
                    help="21-character encryption passcode for the keystore (not saved).")
parser.add_argument("--base", "-b",
                    help="Optional prefix for the KERI keystore file location",
                    required=False,
                    default="")
parser.add_argument("--account-oobi", "-o", help="out-of-band introduciton to load", required=True)
parser.add_argument("--account-username", help="alias for AID resolved from out-of-band introduciton",
                    required=False, default=None)
parser.add_argument("--dbhost", action="store", required=False, default=None)
parser.add_argument("--dbname", action="store", required=False, default=None)
parser.add_argument("--dbuser", action="store", required=False, default=None)
parser.add_argument("--dbpass", action="store", required=False, default=None)


OOBI_RE = re.compile(r'\A/oobi/(?P<cid>[^/]+)(?:/(?P<role>[^/]+)(?:/(?P<eid>[^/]+))?)?\Z', re.IGNORECASE)


def create(args):

    with existing.existingHab(args.alias, args.name, args.base, args.bran) as (hby, hab):

        purl = parse.urlparse(args.account_oobi)

        match = OOBI_RE.match(purl.path)
        if not match:
            raise ValueError("Invalid OOBI format")


        account_aid = match.group("cid")

        response = requests.get(args.account_oobi)
        hab.psr.parse(ims=response.content)

        if account_aid not in hab.kevers:
            raise ConfigurationError("Unable to resolve provided OOBI. Please check your configuration")

        db_host = args.dbhost if args.dbhost else "mongodb://localhost:27017"
        db_name = args.dbname if args.dbname else "castellan"
        db_user = args.dbuser if args.dbuser else None
        db_pass = args.dbpass if args.dbpass else None

        databaseInit(host=db_host, name=db_name, username=db_user, password=db_pass)
        account_svc = AccountService(parser=hab.psr, kvy=hab.kvy)

        doc = dict(aid=account_aid, username=args.account_username)
        kel = hab.replyToOobi(aid=account_aid, role="controller")

        account_svc.create_account(doc, kel)

        print(f"Account {args.account_username} created successfully with AID {account_aid}")

