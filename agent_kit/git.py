"""Git repository discovery and inspection."""

import os
import subprocess
from pathlib import Path

from . import InitError

SKIP_DIRS = {".worktrees", "node_modules", ".venv", "venv", "vendor", "target", "build", "dist"}


def git_root(path):
    if not path.is_dir():
        raise InitError(f"{path} is not a directory")
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise InitError(f"{path} is not inside a Git repository")
    return Path(result.stdout.strip()).resolve()


def git_common_dir(repo):
    result = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=repo,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise InitError(f"{repo}: git rev-parse failed: {result.stderr.strip()}")
    return (repo / result.stdout.strip()).resolve()


def tracked_paths(repo, paths):
    found = []
    for path in paths:
        result = subprocess.run(["git", "ls-files", "--error-unmatch", "--", path], cwd=repo,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            found.append(path)
    return found


def find_repos(root, max_depth=3):
    """Find Git repositories without descending into a repository once found."""
    found = []
    for dirpath, dirnames, _ in os.walk(root):
        path = Path(dirpath)
        if (path / ".git").exists():
            found.append(path)
            dirnames.clear()
            continue
        if len(path.relative_to(root).parts) >= max_depth:
            dirnames.clear()
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS)
    return found
