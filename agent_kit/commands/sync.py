"""Synchronize deterministic changes across managed repositories."""

from pathlib import Path

from .. import InitError
from .init import run_all


def run(args):
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        raise InitError(f"{root} is not a directory")
    return run_all(root, args)


def register(subparsers):
    parser = subparsers.add_parser("sync", help="re-apply deterministic rules to existing agent-kit repositories")
    parser.add_argument("root", nargs="?", default=".", help="directory to scan (default: current dir)")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 if any repository needs attention")
    output.add_argument("--dry-run", action="store_true", help="write nothing; print the diffs")
    parser.set_defaults(func=run)
