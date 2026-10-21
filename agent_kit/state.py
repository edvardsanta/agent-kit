"""Machine-local record of the repositories agent-kit manages, so `sync --known` can find them."""

import os
from pathlib import Path

from . import log


def state_dir():
    configured = os.environ.get("AGENT_KIT_STATE")
    if configured:
        return Path(configured).expanduser()
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "agent-kit"


def repos_file():
    return state_dir() / "repos"


def known_repos():
    """Recorded repositories, in the order they were first seen."""
    try:
        lines = repos_file().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [Path(line) for line in dict.fromkeys(line.strip() for line in lines) if line]


def remember_repos(repos):
    """Record repositories; a failure only costs `sync --known` coverage, so it never stops a run."""
    known = known_repos()
    new = [repo for repo in repos if repo not in known]
    if not new:
        return
    try:
        repos_file().parent.mkdir(parents=True, exist_ok=True)
        repos_file().write_text("".join(f"{repo}\n" for repo in known + new), encoding="utf-8")
    except OSError as error:
        log(f"WARNING: could not record {', '.join(map(str, new))} in {repos_file()}: {error}")
