# -*- encoding: utf-8 -*-
"""
castellan.app.cli.commands.oobi.start module

Launch the castellan OOBI service.
"""

import argparse
import logging

from hio.base import doing
from keri import __version__, help

from castellan.app import oobi_serving

parser = argparse.ArgumentParser(description="Launch the castellan OOBI service")
parser.set_defaults(handler=lambda args: launch(args))
parser.add_argument(
    "-V",
    "--version",
    action="version",
    version=__version__,
    help="Print version and exit.",
)
parser.add_argument(
    "--host",
    "-H",
    action="store",
    default="0.0.0.0",
    help="HTTP server bind address (default 0.0.0.0).",
)
parser.add_argument(
    "--port",
    action="store",
    type=int,
    default=5924,
    help="HTTP server port (default 5924).",
)
parser.add_argument(
    "--loglevel",
    action="store",
    required=False,
    default="INFO",
    help="Log level: DEBUG | INFO | WARNING | ERROR | CRITICAL (default INFO).",
)
parser.add_argument(
    "--logfile",
    action="store",
    required=False,
    default=None,
    help="Path of the log file. Logs are written to stdout if not set.",
)
parser.add_argument("--dbhost", action="store", required=False, default=None)
parser.add_argument("--dbname", action="store", required=False, default=None)
parser.add_argument("--dbuser", action="store", required=False, default=None)
parser.add_argument("--dbpass", action="store", required=False, default=None)

FORMAT = "%(asctime)s [castellan] %(levelname)-8s %(message)s"


def launch(args):
    help.ogler.level = logging.getLevelName(args.loglevel)
    base_formatter = logging.Formatter(FORMAT)
    base_formatter.default_msec_format = None
    help.ogler.baseConsoleHandler.setFormatter(base_formatter)
    help.ogler.level = logging.getLevelName(args.loglevel)

    if args.logfile is not None:
        help.ogler.headDirPath = args.logfile
        help.ogler.reopen(name="castellan", temp=False, clear=True)

    logger = help.ogler.getLogger()
    logger.info(
        "******* Starting castellan OOBI service on %s:%s. *******",
        args.host,
        args.port,
    )

    run_service(args)

    logger.info("******* Ended castellan OOBI service. *******")


def run_service(args, expire=0.0):
    doers = oobi_serving.setup(
        host=args.host,
        port=args.port,
        dbhost=args.dbhost,
        dbname=args.dbname,
        dbuser=args.dbuser,
        dbpass=args.dbpass,
    )

    tock = 0.00125
    doist = doing.Doist(limit=expire, tock=tock, real=True)
    doist.do(doers=doers)
