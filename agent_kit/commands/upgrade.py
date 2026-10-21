"""Upgrade agent-kit itself with the tool that installed it."""

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from .. import InitError, VERSION, log
from .uninstall import WINDOWS, detect_install, finish_in_background, installer_tool

REPO = "edvardsanta/agent-kit"


def latest_release():
    """Tag of the most recent release, pre-releases included (what install.sh picks)."""
    url = f"https://api.github.com/repos/{REPO}/releases?per_page=1"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            releases = json.load(response)
    except (OSError, ValueError) as error:
        raise InitError(f"could not look up the latest release ({error}); pass --version TAG")
    if not releases:
        raise InitError("no release found; pass --version TAG")
    return releases[0]["tag_name"]


def base_python(prefix):
    """The interpreter the venv at `prefix` was created from, read from its pyvenv.cfg."""
    config = {}
    if (prefix / "pyvenv.cfg").is_file():
        for line in (prefix / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            config[key.strip()] = value.strip()
    candidates = [config.get("executable")]
    if config.get("home"):
        candidates += [str(Path(config["home"]) / name) for name in ("python3", "python.exe")]
    return next((path for path in candidates if path and Path(path).is_file()), None)


def plan_upgrade(prefix, source):
    """The command that reinstalls agent-kit from `source` the same way it was installed."""
    method, _ = detect_install(prefix)
    if method in ("uv", "pipx"):
        command = [installer_tool("uv"), "tool", "install", "--force", "--reinstall"] if method == "uv" \
            else [installer_tool("pipx"), "install", "--force"]
        # keep the interpreter: pipx reuses the venv, and another Python breaks its stdlib
        python = base_python(prefix)
        return command + (["--python", python] if python else []) + [source]
    # the install.sh / install.ps1 venv: its shims point into it, so they keep working
    return [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
            "--force-reinstall", source]


def run(args):
    prefix = Path(sys.prefix).resolve()
    # AGENT_KIT_SOURCE: same override as the installers, e.g. a checkout path
    source = os.environ.get("AGENT_KIT_SOURCE")
    if not source:
        tag = args.version or latest_release()
        if tag.removeprefix("v") == VERSION:
            log(f"agent-kit {VERSION} is already the latest release")
            return 0
        source = f"git+https://github.com/{REPO}@{tag}"
    command = plan_upgrade(prefix, source)
    # the new version brings new managed files, so it syncs the known repositories; the command
    # path stays the same across the reinstall
    executable = None if args.no_sync else shutil.which("agent-kit")
    sync = [executable, "sync", "--known"] if executable else None
    if args.dry_run:
        print(f"would run `{subprocess.list2cmdline(command)}`")
        if sync:
            print(f"then `{subprocess.list2cmdline(sync)}`")
        return 0
    if WINDOWS:
        # the running agent-kit.exe cannot be replaced, so a detached cmd does it after we exit
        finish_in_background(command, [], then=sync)
        log("upgrading" + (" and syncing your repositories" if sync else "")
            + "; it finishes in the background in a few seconds")
        return 0
    result = subprocess.run(command)
    if result.returncode != 0:
        raise InitError(f"`{subprocess.list2cmdline(command)}` failed with exit code {result.returncode}")
    log(f"agent-kit was upgraded from {VERSION}; run `agent-kit --version` to check")
    if sync:
        if subprocess.run(sync).returncode != 0:
            log("WARNING: the upgrade worked, but syncing your repositories failed; see above, then "
                "run `agent-kit sync --known` again")
    elif not args.no_sync:
        log("agent-kit is not on PATH, so no repository was synced; run `agent-kit sync --known`")
    return 0


def register(subparsers):
    parser = subparsers.add_parser("upgrade", help="install the latest agent-kit release")
    parser.add_argument("--version", metavar="TAG",
                        help="release tag to install instead of the latest (e.g. v0.1.0)")
    parser.add_argument("--no-sync", action="store_true",
                        help="do not run `agent-kit sync --known` with the new version afterwards")
    parser.add_argument("--dry-run", action="store_true", help="print the commands that would run")
    parser.set_defaults(func=run)
