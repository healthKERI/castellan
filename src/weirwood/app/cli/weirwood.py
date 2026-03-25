# -*- encoding: utf-8 -*-
"""
weirwood.app.cli.weirwood module

Entry point for the weirwood CLI.
"""
import multicommand
from keri import help

from weirwood.app.cli import commands

logger = help.ogler.getLogger()


def main():
    parser = multicommand.create_parser(commands)
    args = parser.parse_args()

    if not hasattr(args, "handler"):
        parser.print_help()
        return

    try:
        args.handler(args)
    except Exception as ex:
        import os
        if os.getenv("DEBUG_WEIRWOOD"):
            import traceback
            traceback.print_exc()
        else:
            print(f"ERR: {ex}")
        return -1


if __name__ == "__main__":
    main()