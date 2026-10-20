"""Shared public API for agent-kit."""

import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
VERSION = "0.2.0"


class InitError(Exception):
    """A user-facing error that should exit with status 2."""


def log(message):
    print(f"[agent-kit] {message}", file=sys.stderr)


# Keep the small Python API used by the test suite and existing integrations.
from .changes import Changes  # noqa: E402,F401
from .languages import (  # noqa: E402,F401
    LANGS,
    render_block,
    rules_file,
    saved_languages,
    saved_langs,
    upsert_block,
)
from .commands.init import CLAUDE_MD, ensure_ignored, plan  # noqa: E402,F401
