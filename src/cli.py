"""The command-line interface for ``iprate``."""

import argparse
import sys
from http.client import HTTPException

from . import __version__
from .api import InvalidResponse, get_public_ipv4
from .tui import TerminalUnavailable, run_screen


def _interactive(parser: argparse.ArgumentParser) -> None:
    """Open the terminal interface and report terminal setup failures."""
    try:
        run_screen()
    except TerminalUnavailable as error:
        parser.exit(1, f"iprate: {error}\n")
    except KeyboardInterrupt:
        parser.exit(130)


def run() -> None:
    """Handle arguments and exit with a nonzero status on failure."""
    parser = argparse.ArgumentParser(
        prog="iprate", description="Check the reputation of your public IPv4."
    )
    parser.add_argument(
        "--ip", action="store_true", help="print the public IPv4 and exit"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    args = parser.parse_args()

    if not args.ip:
        _interactive(parser)
        return

    try:
        address = get_public_ipv4()
    except (OSError, HTTPException, InvalidResponse) as error:
        text = str(error)
        message = "".join(char if char.isprintable() else " " for char in text)
        parser.exit(1, f"iprate: ipify: {message}\n")
    except KeyboardInterrupt:
        parser.exit(130, "iprate: Interrupted.\n")

    sys.stdout.write(f"{address}\n")
