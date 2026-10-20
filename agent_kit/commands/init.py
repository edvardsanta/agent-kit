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
from ..git import find_repos, git_common_dir, git_root, tracked_paths
from ..languages import END, LANGS, MARKER_RE, has_marker, render_block, saved_languages, upsert_block

AI_MEMORY_START = "<!-- ai-memory:start -->"
SUSPICIOUS_RE = re.compile(
    r"https?://|\b(curl|wget|sudo|eval|base64|chmod|chown|ssh|scp|nc)\b|\|\s*(ba|z)?sh\b"
    r"|hooks?\b|allowedTools|permission|settings(\.local)?\.json|\.mcp\.json"
    r"|ignore (all |any )?(previous|prior|above)|api[_ -]?key|token|secret|password", re.I)

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
    if hide_agent_files:
        for name in ("AGENTS.md", "CLAUDE.md", "AGENTS.md.bak-*", ".agents/"):
            ensure_ignored(changes, name, False)
    ensure_no_coauthor(changes)
    return changes


def install_ai_memory(repo, full, skills):
    if not shutil.which("ai-memory"):
        log("WARNING: ai-memory not found in PATH; routing block skipped")
        return
    command = ["ai-memory", "install-instructions", "--target", "AGENTS.md"]
    if not full:
        command.append("--compact")
    if not skills:
        command.append("--no-skills")
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True)
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
    prompt = (KIT / "prompts" / "fill.md").read_text().replace("{{LANG_NAME}}", LANGS[docs_lang])
    if migrate:
        prompt += "\n" + (KIT / "prompts" / "migrate.md").read_text()
    answer = ask_repo_agent(repo, agent, prompt, trust, "analyzing the repo to fill project sections")
    return parse_sections(answer)


def add_project_sections(changes, sections):
    path = changes.repo / "AGENTS.md"
    text = changes.read(path)
    head, old, tail = split_agents_md(text)
    new = f"{head}\n\n{sections}\n" + (f"\n{tail}" if tail else "")
    changes.write(path, new, "AGENTS.md: project sections written")
    return suspicious_lines(old, sections)


def resolve_languages(repo, args):
    old_docs, old_chat, old_git = saved_languages(repo)
    if args.lang and (args.docs_lang or args.chat_lang):
        raise InitError("--lang cannot be combined with --docs-lang or --chat-lang")
    if args.lang:
        log("NOTE: --lang is the legacy alias for --docs-lang plus --chat-lang")
    docs_lang = args.docs_lang or args.lang or old_docs or "pt"
    chat_lang = args.chat_lang or args.lang or old_chat or docs_lang
    git_lang = args.git_lang or (args.lang if args.lang else old_git) or docs_lang
    return docs_lang, chat_lang, git_lang


def check_existing_claude(repo, args):
    path = repo / "CLAUDE.md"
    if not path.exists() or "@AGENTS.md" in path.read_text() or args.migrate_claude or args.keep_claude:
        return
    raise InitError(
        "CLAUDE.md exists but does not import AGENTS.md; no files were changed. "
        "Rerun with --migrate-claude, or --keep-claude to continue intentionally")


def run_one(repo, args):
    check_existing_claude(repo, args)
    requested_agent = args.agent or "auto"
    if args.migrate_claude and requested_agent == "none":
        raise InitError("--migrate-claude needs an agent to merge CLAUDE.md into AGENTS.md; drop --agent none")
    docs_lang, chat_lang, git_lang = resolve_languages(repo, args)
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
        steps = ["ai-memory install-instructions"]
        if requested_agent != "none":
            steps.append(f"{requested_agent} to fill project sections")
        if args.migrate_claude:
            steps.append("replace CLAUDE.md with the import stub if the agent succeeds")
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
    install_ai_memory(repo, args.full_memory, not args.no_skills)
    if flagged:
        log("REVIEW: the agent wrote lines that run commands, fetch URLs or touch permissions; "
            "check they come from the project and not from injected text:")
        for line in flagged:
            log(f"  | {line.strip()}")
    log("done. Review with `git diff` / `git status`; nothing was committed.")
    return 0


def run_all(root, args):
    checked = current = outdated = skipped = errors = 0
    for repo in find_repos(root):
        if not has_marker(repo):
            continue
        checked += 1
        name = os.path.relpath(repo, root)
        docs_lang, chat_lang, git_lang = saved_languages(repo)
        if not docs_lang:
            skipped += 1
            log(f"SKIP {name}: marker has no saved language; run `agent-kit init {repo} --docs-lang <pt|en>` once")
            continue
        try:
            changes = plan(repo, docs_lang, git_lang or docs_lang, chat_lang or docs_lang)
        except InitError as error:
            log(f"ERROR {name}: {error}")
            errors += 1
            continue
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
    changed_label = "outdated" if args.check else "would update" if args.dry_run else "updated"
    log(f"Checked {checked} repositories: {current} current, {outdated} {changed_label}, "
        f"{skipped} need migration, {errors} errors.")
    return 1 if errors or (args.check and (outdated or skipped)) else 0


def apply_profile(repo, args):
    if args.profile == "upstream":
        if args.tracked:
            raise InitError("--profile upstream cannot be combined with --tracked")
        if args.trust:
            raise InitError("--profile upstream cannot be combined with --trust")
        args.hide_agent_files = True
        args.no_skills = True
    elif args.profile == "own":
        if args.hide_agent_files:
            raise InitError("--profile own cannot be combined with --hide-agent-files")
        args.tracked = True
    elif args.hide_agent_files:
        args.no_skills = True
    if args.hide_agent_files:
        tracked = tracked_paths(repo, ["AGENTS.md", "CLAUDE.md", ".claude/settings.local.json"])
        if tracked:
            names = ", ".join(tracked)
            raise InitError(
                f"upstream tracks {names}, so local changes cannot be hidden; no files were changed. "
                "Use --profile own to modify tracked instructions, or continue without agent-kit")


def run(args):
    target = Path(args.repo).expanduser().resolve()
    if args.all:
        values = (("--lang", args.lang), ("--docs-lang", args.docs_lang),
                  ("--chat-lang", args.chat_lang), ("--git-lang", args.git_lang),
                  ("--profile", args.profile), ("--agent", args.agent),
                  ("--migrate-claude", args.migrate_claude), ("--full-memory", args.full_memory),
                  ("--tracked", args.tracked), ("--hide-agent-files", args.hide_agent_files),
                  ("--no-skills", args.no_skills), ("--trust", args.trust),
                  ("--keep-claude", args.keep_claude))
        incompatible = [flag for flag, value in values if value]
        if incompatible:
            raise InitError(f"--all only re-applies the deterministic part; not compatible with {', '.join(incompatible)}")
        if not target.is_dir():
            raise InitError(f"{target} is not a directory")
        return run_all(target, args)
    target = git_root(target)
    apply_profile(target, args)
    return run_one(target, args)


def register(subparsers):
    parser = subparsers.add_parser("init", help="set up or update a repository (what `agent-init` runs)")
    parser.add_argument("repo", nargs="?", default=".",
                        help="target repository, or the root to scan with --all (default: current dir)")
    parser.add_argument("--profile", choices=["own", "upstream"],
                        help="safe defaults for your repository or a third-party clone")
    parser.add_argument("--chat-lang", choices=LANGS, help="language agents use to talk with you")
    parser.add_argument("--docs-lang", choices=LANGS,
                        help="documentation and managed-rules language (default: saved value, else pt)")
    parser.add_argument("--git-lang", choices=LANGS,
                        help="language of commits/issues/PRs (default: saved value, else docs language)")
    parser.add_argument("--lang", choices=LANGS, help="legacy alias for --chat-lang plus --docs-lang")
    parser.add_argument("--agent", choices=["auto", "claude", "codex", "none"],
                        help="who fills project sections (default: auto, Claude then Codex)")
    parser.add_argument("--full-memory", action="store_true",
                        help="inline the full ai-memory guidance instead of --compact")
    parser.add_argument("--tracked", action="store_true",
                        help="put .worktrees/ in the tracked .gitignore instead of .git/info/exclude")
    parser.add_argument("--hide-agent-files", action="store_true",
                        help="also exclude AGENTS.md/CLAUDE.md locally (upstream forks)")
    claude_mode = parser.add_mutually_exclusive_group()
    claude_mode.add_argument("--migrate-claude", action="store_true",
                             help="move an existing CLAUDE.md into AGENTS.md and replace it with the import stub")
    claude_mode.add_argument("--keep-claude", action="store_true",
                             help="keep an independent existing CLAUDE.md intentionally")
    parser.add_argument("--no-skills", action="store_true",
                        help="do not install ai-memory skills into the project")
    parser.add_argument("--trust", action="store_true",
                        help="allow the agent to load the target repo's Claude config and MCP servers")
    parser.add_argument("--all", action="store_true",
                        help="re-apply deterministic changes to every managed repo below REPO")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--check", action="store_true",
                        help="write nothing; list what is outdated and exit 1 if anything is")
    output.add_argument("--dry-run", action="store_true",
                        help="write nothing; print the diff of what would change")
    parser.set_defaults(func=run)
