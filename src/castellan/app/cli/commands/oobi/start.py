# -*- encoding: utf-8 -*-
"""
castellan.app.cli.commands.oobi.start module

Launch the castellan OOBI service using uvicorn.
"""

import argparse
import logging
import os

from keri import __version__, help

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
    "--workers",
    action="store",
    type=int,
    default=1,
    help="Number of worker processes (default 1).",
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
    import uvicorn

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
        "******* Starting castellan OOBI service on %s:%s *******",
        args.host,
        args.port,
    )

    # Set environment variables for app configuration
    if args.dbhost:
        os.environ["CASTELLAN_DBHOST"] = args.dbhost
    if args.dbname:
        os.environ["CASTELLAN_DBNAME"] = args.dbname
    if args.dbuser:
        os.environ["CASTELLAN_DBUSER"] = args.dbuser
    if args.dbpass:
        os.environ["CASTELLAN_DBPASS"] = args.dbpass

    # Run uvicorn
    uvicorn.run(
        "castellan.app.oobi_serving:app",
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level=args.loglevel.lower(),
        reload=False,
    )

    logger.info("******* Ended castellan OOBI service. *******")
