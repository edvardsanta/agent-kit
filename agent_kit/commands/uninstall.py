"""Remove agent-kit itself, undoing what its installer or Python tool installer did."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .. import InitError, log
from ..languages import user_rules_dir

# written by install.sh / install.ps1 into their private venv; holds the directory of the shims
INSTALL_MARKER = "agent-kit-install"
WINDOWS = os.name == "nt"


def detect_install(prefix):
    """How the running agent-kit was installed, as (method, details)."""
    if (prefix / "uv-receipt.toml").is_file():
        return "uv", None
    if (prefix / "pipx_metadata.json").is_file():
        return "pipx", None
    marker = prefix / INSTALL_MARKER
    if marker.is_file():
        # utf-8-sig: Windows PowerShell 5.1 writes UTF-8 with a BOM
        return "installer", Path(marker.read_text(encoding="utf-8-sig").strip())
    raise InitError(
        f"could not tell how agent-kit was installed (Python prefix {prefix}); manage it with the "
        "tool you used, e.g. `python -m pip uninstall agent-kit`, or delete the `make install` "
        "symlinks")


def installer_tool(method):
    tool = shutil.which(method)
    if not tool:
        raise InitError(f"agent-kit was installed with {method}, but {method} is not on PATH")
    return tool


def plan_uninstall(prefix, purge=False, environ=None):
    """Return the steps as (description, command or None, paths to delete, PATH entry to drop)."""
    environ = os.environ if environ is None else environ
    method, bin_dir = detect_install(prefix)
    command, paths, path_entry = None, [], None
    if method in ("uv", "pipx"):
        tool = installer_tool(method)
        command = [tool, "tool", "uninstall", "agent-kit"] if method == "uv" else \
            [tool, "uninstall", "agent-kit"]
        description = f"run `{method} {' '.join(command[1:])}`"
    else:
        data_dir = prefix.parent
        if WINDOWS:
            paths.append(data_dir)
            path_entry = str(bin_dir)
        else:
            # only shims that point into this installation
            for name in ("agent-kit", "agent-init"):
                shim = bin_dir / name
                if shim.is_symlink() and Path(os.path.realpath(shim)).is_relative_to(prefix):
                    paths.append(shim)
            paths.append(data_dir)
        description = "delete " + ", ".join(str(path) for path in paths)
        if path_entry:
            description += f" and drop {path_entry} from the user PATH"
    if purge:
        if environ.get("AGENT_KIT_RULES"):
            log(f"--purge keeps {user_rules_dir()} because AGENT_KIT_RULES points there; "
                "delete it yourself")
        elif user_rules_dir().exists():
            paths.append(user_rules_dir().parent)
            description += f"; delete your rules in {user_rules_dir().parent}"
    return description, command, paths, path_entry


def remove_user_path_entry(entry):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                        winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            value, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            return
        same = os.path.normcase(entry.rstrip("\\"))
        kept = [part for part in value.split(";")
                if part and os.path.normcase(part.rstrip("\\")) != same]
        winreg.SetValueEx(key, "Path", 0, kind, ";".join(kept))


def finish_in_background(command, paths):
    """Windows cannot delete the running agent-kit.exe, so a detached cmd does it after we exit."""
    steps = ["ping -n 3 127.0.0.1 >nul"]
    if command:
        steps.append(subprocess.list2cmdline(command))
    steps += [f'rmdir /s /q "{path}"' if path.is_dir() else f'del /f /q "{path}"' for path in paths]
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    # one string, not a list: list2cmdline would escape the inner quotes as \" and cmd misreads them;
    # /s makes cmd strip exactly the outer pair
    subprocess.Popen(f'cmd /d /s /c "{" & ".join(steps)}"', creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def confirm(description, assume_yes):
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise InitError("uninstall needs confirmation; pass --yes when input is not interactive")
    print(f"agent-kit will {description}. Continue? [y/N] ", end="", file=sys.stderr, flush=True)
    if input().strip().lower() not in ("y", "yes"):
        raise InitError("uninstall cancelled; nothing was changed")


def run(args):
    prefix = Path(sys.prefix).resolve()
    description, command, paths, path_entry = plan_uninstall(prefix, args.purge)
    if args.dry_run:
        print(f"would {description}")
        return 0
    confirm(description, args.yes)
    if path_entry:
        remove_user_path_entry(path_entry)
    if WINDOWS:
        finish_in_background(command, paths)
        log("uninstalling; it finishes in the background in a few seconds")
        return 0
    if command:
        result = subprocess.run(command)
        if result.returncode != 0:
            raise InitError(f"`{' '.join(command)}` failed with exit code {result.returncode}")
    for path in paths:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    log("agent-kit was uninstalled")
    return 0


def register(subparsers):
    parser = subparsers.add_parser("uninstall", help="remove agent-kit from this machine")
    parser.add_argument("--purge", action="store_true",
                        help="also delete your personal rules in the agent-kit config directory")
    parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    parser.add_argument("--dry-run", action="store_true", help="print what would be removed")
    parser.set_defaults(func=run)
