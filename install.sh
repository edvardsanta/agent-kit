#!/bin/sh
# Install or upgrade agent-kit on Linux and macOS.
#
#   curl -fsSL https://raw.githubusercontent.com/edvardsanta/agent-kit/main/install.sh | sh
#
# Environment:
#   AGENT_KIT_VERSION    tag to install (default: the most recent release, pre-releases included)
#   AGENT_KIT_SOURCE     pip requirement to install instead of the GitHub tag (e.g. a checkout path)
#   AGENT_KIT_INSTALLER  uv, pipx or venv (default: the first of uv, pipx found, else venv)
set -eu

REPO=edvardsanta/agent-kit
DATA_DIR=${XDG_DATA_HOME:-$HOME/.local/share}/agent-kit
BIN_DIR=$HOME/.local/bin

say() { printf '[agent-kit] %s\n' "$*" >&2; }
die() { printf 'agent-kit install: error: %s\n' "$*" >&2; exit 2; }

command -v git >/dev/null 2>&1 || die "git is required; install it and run this again"

PYTHON=
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
        "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        PYTHON=$candidate
        break
    fi
done
[ -n "$PYTHON" ] || die "Python 3.10 or newer is required"

if [ -n "${AGENT_KIT_SOURCE:-}" ]; then
    SOURCE=$AGENT_KIT_SOURCE
else
    VERSION=${AGENT_KIT_VERSION:-}
    if [ -z "$VERSION" ]; then
        VERSION=$("$PYTHON" -c '
import json, sys, urllib.request
url = f"https://api.github.com/repos/{sys.argv[1]}/releases?per_page=1"
releases = json.load(urllib.request.urlopen(url, timeout=30))
print(releases[0]["tag_name"] if releases else "")
' "$REPO") || die "could not look up the latest release; set AGENT_KIT_VERSION"
        [ -n "$VERSION" ] || die "no release found; set AGENT_KIT_VERSION"
    fi
    SOURCE="git+https://github.com/$REPO@$VERSION"
fi

INSTALLER=${AGENT_KIT_INSTALLER:-}
if [ -z "$INSTALLER" ]; then
    if command -v uv >/dev/null 2>&1; then
        INSTALLER=uv
    elif command -v pipx >/dev/null 2>&1; then
        INSTALLER=pipx
    else
        INSTALLER=venv
    fi
fi
case $INSTALLER in
    uv | pipx | venv) ;;
    *) die "AGENT_KIT_INSTALLER must be uv, pipx or venv" ;;
esac

say "installing $SOURCE with $INSTALLER"
case $INSTALLER in
    uv)
        uv tool install --force --python "$PYTHON" "$SOURCE"
        ;;
    pipx)
        pipx install --force --python "$PYTHON" "$SOURCE"
        ;;
    venv)
        # a private venv avoids "externally managed" system Pythons (PEP 668)
        rm -rf "$DATA_DIR/venv"
        "$PYTHON" -m venv "$DATA_DIR/venv"
        "$DATA_DIR/venv/bin/python" -m pip install --quiet --disable-pip-version-check "$SOURCE"
        mkdir -p "$BIN_DIR"
        ln -sf "$DATA_DIR/venv/bin/agent-kit" "$BIN_DIR/agent-kit"
        ln -sf "$DATA_DIR/venv/bin/agent-init" "$BIN_DIR/agent-init"
        ;;
esac

if command -v agent-kit >/dev/null 2>&1; then
    say "installed $(agent-kit --version)"
else
    say "installed, but agent-kit is not on PATH yet; add $BIN_DIR to PATH and reopen the shell"
fi
