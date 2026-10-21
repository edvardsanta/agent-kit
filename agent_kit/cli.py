"""Command-line assembly for agent-kit."""

import argparse
import sys
from pathlib import Path

from . import InitError, VERSION
from .commands import doctor, init, procedures, rules, sync, uninstall

DESCRIPTION = """agent-kit: standardize AGENTS.md / CLAUDE.md across projects.

`init` sets up one repository, `sync` updates managed repositories, and resource
commands manage rules and reusable project procedures.
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="agent-kit", description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"agent-kit {VERSION}")
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    init.register(subparsers)
    sync.register(subparsers)
    rules.register(subparsers)
    procedures.register(subparsers)
    doctor.register(subparsers)
    uninstall.register(subparsers)
    return parser


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    # Windows encodes a redirected stdout/stderr with the locale code page (cp1252), which cannot
    # print most of the Unicode found in rules and diffs
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if Path(sys.argv[0]).stem == "agent-init" and argv != ["--version"]:
        argv = ["init", *argv]
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except InitError as error:
        print(f"agent-kit: error: {error}", file=sys.stderr)
        return 2
