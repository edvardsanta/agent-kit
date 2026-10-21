"""Synchronize deterministic changes across managed repositories."""

from pathlib import Path

from .. import InitError, log
from ..git import find_repos
from ..state import known_repos, repos_file
from .init import run_all


def run(args):
    if args.known:
        if args.root:
            raise InitError("pass a ROOT or --known, not both")
        repos = known_repos()
        if not repos:
            log(f"no known repositories in {repos_file()}; run `agent-kit sync <folder>` once, or "
                "`agent-init` in a repository, to record them")
            return 0
        return run_all(repos, args)
    root = Path(args.root or ".").expanduser().resolve()
    if not root.is_dir():
        raise InitError(f"{root} is not a directory")
    return run_all(find_repos(root), args, base=root)


def register(subparsers):
    parser = subparsers.add_parser("sync", help="re-apply deterministic rules to existing agent-kit repositories")
    parser.add_argument("root", nargs="?", help="directory to scan (default: current dir)")
    parser.add_argument("--known", action="store_true",
                        help="sync the repositories recorded by earlier init/sync runs instead of scanning")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 if any repository needs attention")
    output.add_argument("--dry-run", action="store_true", help="write nothing; print the diffs")
    parser.set_defaults(func=run)
