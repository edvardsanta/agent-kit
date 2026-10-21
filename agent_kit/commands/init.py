"""Initialize one repository and maintain its managed instructions."""

import difflib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .. import KIT, InitError, log
from ..agents import ask_repo_agent, select_agent
from ..changes import Changes
from ..git import git_common_dir, git_root, tracked_paths
from ..languages import (END, LANGS, MARKER_RE, has_marker, render_block, resolve_languages,
                         saved_languages, upsert_block)
from ..state import remember_repos

AI_MEMORY_START = "<!-- ai-memory:start -->"
SUSPICIOUS_RE = re.compile(
    r"https?://|\b(curl|wget|sudo|eval|base64|chmod|chown|ssh|scp|nc)\b|\|\s*(ba|z)?sh\b"
    r"|hooks?\b|allowedTools|permission|settings(\.local)?\.json|\.mcp\.json"
    r"|ignore (all |any )?(previous|prior|above)|api[_ -]?key|token|secret|password", re.I)

# project skill folders read by Claude Code and by Codex
SKILL_ROOTS = (".claude/skills", ".agents/skills")

CLAUDE_MD = """@AGENTS.md

## Claude Code notes

- `AGENTS.md` is canonical; edit rules there, not here. The ai-memory routing block lives
  in `AGENTS.md` and is loaded through the import above (do not add a second copy here).
"""


def ensure_ignored(changes, entry, tracked):
    tracked_gitignore = changes.repo / ".gitignore"
    gitignore = tracked_gitignore if tracked else git_common_dir(changes.repo) / "info" / "exclude"
    for path in {gitignore, tracked_gitignore}:
        lines = (changes.read(path) or "").splitlines()
        if entry in lines or entry.rstrip("/") in lines:
            return
    lines = (changes.read(gitignore) or "").splitlines()
    changes.write(gitignore, "\n".join(lines + [entry]) + "\n", f"{gitignore.name}: added {entry}")


def ensure_agents_md(changes, block):
    path = changes.repo / "AGENTS.md"
    old = changes.read(path)
    changes.write(path, upsert_block(old, block), f"AGENTS.md: {'created' if old is None else 'updated'}")


def ensure_claude_md(changes, keep_existing=False):
    path = changes.repo / "CLAUDE.md"
    text = changes.read(path)
    if text is None:
        changes.write(path, CLAUDE_MD, "CLAUDE.md: created (imports AGENTS.md)")
    elif "@AGENTS.md" not in text and not keep_existing:
        raise InitError("CLAUDE.md exists but does not import AGENTS.md; use --migrate-claude or --keep-claude")


def ensure_skills(changes):
    """Copy the packaged agent skills where Claude Code (.claude/) and Codex (.agents/) find them."""
    for source in sorted((KIT / "skills").glob("*/SKILL.md")):
        text = source.read_text(encoding="utf-8")
        for root in SKILL_ROOTS:
            path = changes.repo / root / source.parent.name / "SKILL.md"
            changes.write(path, text, f"{changes.rel(path)}: {'updated' if path.exists() else 'created'}")


def ensure_no_coauthor(changes):
    path = changes.repo / ".claude" / "settings.local.json"
    text = changes.read(path)
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError as error:
        raise InitError(f"{changes.rel(path)}: invalid JSON ({error}); fix it and run again")
    if not isinstance(data, dict) or not isinstance(data.get("attribution", {}), dict):
        raise InitError(f"{changes.rel(path)}: expected an object with an `attribution` object; fix it and run again")
    ensure_ignored(changes, ".claude/settings.local.json", False)
    attribution = data.setdefault("attribution", {})
    if attribution.get("commit") == "" and attribution.get("pr") == "":
        return
    attribution.update(commit="", pr="")
    changes.write(path, json.dumps(data, indent=2) + "\n",
                  ".claude/settings.local.json: attribution disabled")


def plan(repo, docs_lang, git_lang, chat_lang=None, tracked=False, hide_agent_files=False,
         migrate=False, keep_claude=False):
    changes = Changes(repo)
    ensure_agents_md(changes, render_block(docs_lang, git_lang, chat_lang, repo))
    if not migrate:
        ensure_claude_md(changes, keep_claude)
    ensure_ignored(changes, ".worktrees/", tracked)
    ensure_skills(changes)
    if hide_agent_files:
        for name in ("AGENTS.md", "CLAUDE.md", "AGENTS.md.bak-*", ".agents/",
                     ".claude/skills/agent-kit-*/"):
            ensure_ignored(changes, name, False)
    ensure_no_coauthor(changes)
    return changes


def install_ai_memory(repo, mode):
    if mode == "off":
        return
    if not shutil.which("ai-memory"):
        log("WARNING: ai-memory not found in PATH; routing block skipped")
        return
    command = ["ai-memory", "install-instructions", "--target", "AGENTS.md"]
    if mode == "compact":
        command.append("--compact")
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
    status = "installed" if result.returncode == 0 else f"FAILED\n{result.stderr.strip()}"
    log(f"ai-memory: routing block {status}")


def split_agents_md(text):
    start = text.index(END) + len(END)
    tail = text.find(AI_MEMORY_START, start)
    tail = len(text) if tail < 0 else tail
    return text[:start], text[start:tail], text[tail:]


def parse_sections(answer):
    match = re.search(r"^=== project sections ===[ \t]*$(.*?)^=== end ===", answer,
                      flags=re.M | re.S)
    if not match:
        raise InitError("agent answer lacks the `=== project sections ===` / `=== end ===` delimiters; AGENTS.md left as is")
    body = re.sub(r"^\s*```\w*\n|\n```\s*$", "", match.group(1).strip("\n")).strip()
    if MARKER_RE.search(body):
        raise InitError("agent answer contains agent-kit/ai-memory markers; AGENTS.md left as is")
    if not re.search(r"^## ", body, flags=re.M):
        raise InitError("agent answer has no `## ` section; AGENTS.md left as is")
    return body


def suspicious_lines(old, new):
    added = [line[1:] for line in difflib.unified_diff(
        old.splitlines(), new.splitlines(), lineterm="")
        if line.startswith("+") and not line.startswith("+++")]
    return [line for line in added if SUSPICIOUS_RE.search(line)]


def generate_project_sections(repo, agent, docs_lang, migrate, trust):
    prompt = (KIT / "prompts" / "fill.md").read_text(encoding="utf-8").replace("{{LANG_NAME}}", LANGS[docs_lang])
    if migrate:
        prompt += "\n" + (KIT / "prompts" / "migrate.md").read_text(encoding="utf-8")
    answer = ask_repo_agent(repo, agent, prompt, trust, "analyzing the repo to fill project sections")
    return parse_sections(answer)


def add_project_sections(changes, sections):
    path = changes.repo / "AGENTS.md"
    text = changes.read(path)
    head, old, tail = split_agents_md(text)
    new = f"{head}\n\n{sections}\n" + (f"\n{tail}" if tail else "")
    changes.write(path, new, "AGENTS.md: project sections written")
    return suspicious_lines(old, sections)


def check_existing_claude(repo, args):
    path = repo / "CLAUDE.md"
    if not path.exists() or "@AGENTS.md" in path.read_text(encoding="utf-8") or args.migrate_claude or args.keep_claude:
        return
    raise InitError(
        "CLAUDE.md exists but does not import AGENTS.md; no files were changed. "
        "Rerun with --migrate-claude, or --keep-claude to continue intentionally")


def run_one(repo, args):
    check_existing_claude(repo, args)
    requested_agent = args.agent or "auto"
    if args.migrate_claude and requested_agent == "none":
        raise InitError("--migrate-claude needs an agent to merge CLAUDE.md into AGENTS.md; drop --agent none")
    docs_lang, chat_lang, git_lang = resolve_languages(repo, args.docs_lang, args.git_lang, args.chat_lang)
    changes = plan(repo, docs_lang, git_lang, chat_lang, args.tracked,
                   args.hide_agent_files, args.migrate_claude, args.keep_claude)
    if args.check:
        if changes.pending:
            log("outdated: " + ", ".join(changes.rel(path) for path in changes.pending))
            return 1
        log("up to date")
        return 0
    if args.dry_run:
        changes.diff()
        steps = [] if args.memory == "off" else [f"ai-memory install-instructions ({args.memory})"]
        if requested_agent != "none":
            steps.append(f"{requested_agent} to fill project sections")
        if args.migrate_claude:
            steps.append("replace CLAUDE.md with the import stub if the agent succeeds")
        if steps:
            log("would also run: " + "; ".join(steps))
        return 0
    agent = select_agent(requested_agent, allow_none=True)
    flagged = []
    if agent != "none":
        sections = generate_project_sections(repo, agent, docs_lang, args.migrate_claude, args.trust)
        flagged = add_project_sections(changes, sections)
    if args.migrate_claude:
        changes.write(repo / "CLAUDE.md", CLAUDE_MD, "CLAUDE.md: replaced with the import stub")
    if agent != "none" and changes.pending:
        changes.diff()
    changes.apply()
    remember_repos([repo])
    install_ai_memory(repo, args.memory)
    if flagged:
        log("REVIEW: the agent wrote lines that run commands, fetch URLs or touch permissions; "
            "check they come from the project and not from injected text:")
        for line in flagged:
            log(f"  | {line.strip()}")
    log("done. Review with `git diff` / `git status`; nothing was committed.")
    return 0


def hides_agent_files(repo):
    """Whether `--profile upstream` initialized the repo: it hid AGENTS.md in the local exclude."""
    exclude = git_common_dir(repo) / "info" / "exclude"
    try:
        return "AGENTS.md" in exclude.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False


def run_all(repos, args, base=None):
    checked = current = outdated = skipped = errors = 0
    synced = []
    for repo in repos:
        name = os.path.relpath(repo, base) if base else str(repo)
        if not repo.is_dir():
            log(f"SKIP {name}: no longer exists")
            continue
        if not has_marker(repo):
            continue
        checked += 1
        docs_lang, chat_lang, git_lang = saved_languages(repo)
        if not docs_lang:
            skipped += 1
            log(f"SKIP {name}: marker has no saved language; run `agent-kit init {repo} --docs-lang <pt|en>` once")
            continue
        try:
            changes = plan(repo, docs_lang, git_lang or docs_lang, chat_lang,
                           hide_agent_files=hides_agent_files(repo))
        except InitError as error:
            log(f"ERROR {name}: {error}")
            errors += 1
            continue
        if not args.check and not args.dry_run:
            synced.append(repo)
        if not changes.pending:
            current += 1
            if not args.check:
                log(f"ok {name}")
            continue
        outdated += 1
        if args.check:
            log(f"outdated {name}: " + ", ".join(changes.rel(path) for path in changes.pending))
        elif args.dry_run:
            changes.diff()
        else:
            log(f"updating {name}")
            changes.apply()
    remember_repos(synced)
    changed_label = "outdated" if args.check else "would update" if args.dry_run else "updated"
    log(f"Checked {checked} repositories: {current} current, {outdated} {changed_label}, "
        f"{skipped} need migration, {errors} errors.")
    return 1 if errors or (args.check and (outdated or skipped)) else 0


def apply_profile(repo, args):
    args.hide_agent_files = False
    if args.profile == "upstream":
        if args.tracked:
            raise InitError("--profile upstream cannot be combined with --tracked")
        if args.trust:
            raise InitError("--profile upstream cannot be combined with --trust")
        args.hide_agent_files = True
        args.memory = args.memory or "off"
    elif args.profile == "own":
        args.tracked = True
    args.memory = args.memory or "compact"
    if args.hide_agent_files:
        tracked = tracked_paths(repo, ["AGENTS.md", "CLAUDE.md", ".claude/settings.local.json"])
        if tracked:
            names = ", ".join(tracked)
            raise InitError(
                f"upstream tracks {names}, so local changes cannot be hidden; no files were changed. "
                "Use --profile own to modify tracked instructions, or continue without agent-kit")


def run(args):
    target = Path(args.repo).expanduser().resolve()
    target = git_root(target)
    apply_profile(target, args)
    return run_one(target, args)


def register(subparsers):
    parser = subparsers.add_parser("init", help="set up or update a repository (what `agent-init` runs)")
    parser.add_argument("repo", nargs="?", default=".",
                        help="target repository (default: current directory)")
    parser.add_argument("--profile", choices=["own", "upstream"],
                        help="safe defaults for your repository or a third-party clone")
    parser.add_argument("--chat-lang", choices=LANGS,
                        help="pin the language agents use to talk with you (default: saved value, else "
                             "no chat rule)")
    parser.add_argument("--docs-lang", choices=LANGS,
                        help="documentation and managed-rules language (default: saved value, else "
                             "detected from README/docs, else the Git language)")
    parser.add_argument("--git-lang", choices=LANGS,
                        help="language of commits/issues/PRs (default: saved value, else detected "
                             "from commit subjects, else the docs language)")
    parser.add_argument("--agent", choices=["auto", "claude", "codex", "none"],
                        help="who fills project sections (default: auto, Claude then Codex)")
    parser.add_argument("--memory", choices=["off", "compact", "full"],
                        help="ai-memory integration level (default: compact; upstream: off)")
    parser.add_argument("--tracked", action="store_true",
                        help="put .worktrees/ in the tracked .gitignore instead of .git/info/exclude")
    claude_mode = parser.add_mutually_exclusive_group()
    claude_mode.add_argument("--migrate-claude", action="store_true",
                             help="move an existing CLAUDE.md into AGENTS.md and replace it with the import stub")
    claude_mode.add_argument("--keep-claude", action="store_true",
                             help="keep an independent existing CLAUDE.md intentionally")
    parser.add_argument("--trust", action="store_true",
                        help="allow the agent to load the target repo's Claude config and MCP servers")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--check", action="store_true",
                        help="write nothing; list what is outdated and exit 1 if anything is")
    output.add_argument("--dry-run", action="store_true",
                        help="write nothing; print the diff of what would change")
    parser.set_defaults(func=run)
