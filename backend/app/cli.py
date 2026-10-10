"""Management CLI.

Usage:
    python -m app.cli make-admin <email>
"""

import argparse
import logging
import sys
from collections.abc import Sequence

from app.database import SessionLocal
from app.services import admin_service

logger = logging.getLogger("app.cli")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make_admin = sub.add_parser("make-admin", help="Grant admin rights to an existing user")
    make_admin.add_argument("email", help="Email of the user to promote")
    return parser


def cmd_make_admin(email: str) -> int:
    """
    Promote the user with ``email`` to admin.

    Args:
        email: Email of an existing user

    Returns:
        Process exit code: 0 on success, 1 if the user was not found.
    """
    with SessionLocal() as db:
        user = admin_service.make_admin(db, email)
    if user is None:
        logger.error("No user found with email %s", email)
        return 1
    logger.info("User %s (id=%s) is now an admin", user.email, user.id)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """
    Parse arguments and dispatch the requested command.

    Args:
        argv: Argument list (defaults to sys.argv[1:])

    Returns:
        Process exit code.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
    args = _build_parser().parse_args(argv)
    if args.command == "make-admin":
        return cmd_make_admin(args.email)
    return 2  # pragma: no cover - argparse enforces a valid subcommand


if __name__ == "__main__":
    sys.exit(main())
