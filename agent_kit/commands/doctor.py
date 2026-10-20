"""Report required and optional local tools."""

import shutil

from .. import InitError, log
from ..languages import user_rules_dir


def run(args):
    checks = {name: shutil.which(name) for name in ("git", "claude", "codex", "ai-memory")}
    for name, path in checks.items():
        print(f"{name}: {path or 'not found'}")
    print(f"rules: {user_rules_dir()}")
    if not checks["git"]:
        raise InitError("git is required")
    if not checks["claude"] and not checks["codex"]:
        log("WARNING: no agent found; init still works with --agent none")
    return 0


def register(subparsers):
    subparsers.add_parser("doctor", help="check required and optional local tools").set_defaults(func=run)
