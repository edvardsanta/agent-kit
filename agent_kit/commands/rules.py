"""Inspect, seed, and update global or project rules."""

import difflib
import re
import sys
from pathlib import Path

from .. import KIT, InitError, log
from ..agents import ask_agent, select_agent
from ..git import git_root
from ..languages import (
    LANGS,
    PROJECT_RULE_HEADINGS,
    project_rules_file,
    rules_file,
    seed_project_rules,
    seed_rules,
    user_rules_dir,
)


def parse_rules_answer(answer, current):
    answer = answer.split("=== end ===")[0]
    parts = re.split(r"^=== (\w+)\.md ===[ \t]*$", answer, flags=re.M)
    found = {parts[index]: re.sub(r"\n```\s*$", "", parts[index + 1].strip("\n")) + "\n"
             for index in range(1, len(parts) - 1, 2)}
    missing = [lang for lang in current if lang not in found]
    if missing:
        raise InitError(f"agent answer has no section for {', '.join(missing)}.md; nothing written")
    for lang, old in current.items():
        new = found[lang]
        for placeholder in ("{{LANG_NAME}}", "{{CHAT_LANG_NAME}}", "{{DOCS_LANG_NAME}}", "{{GIT_LANG_NAME}}"):
            if placeholder in old and placeholder not in new:
                raise InitError(f"agent dropped {placeholder} from {lang}.md; nothing written")
        if new.splitlines()[0] != old.splitlines()[0]:
            raise InitError(f"agent changed the first heading of {lang}.md; nothing written")
    return {lang: found[lang] for lang in current}


def run_add(args):
    scope = getattr(args, "scope", "global")
    repo_arg = getattr(args, "repo", None)
    if repo_arg and scope != "project":
        raise InitError("--repo requires --scope project; no rules were changed")
    if scope == "project":
        repo = git_root(Path(repo_arg or ".").expanduser().resolve())
        directory = repo / ".agent-kit" / "rules"
        current = {lang: (project_rules_file(repo, lang).read_text(encoding="utf-8")
                          if project_rules_file(repo, lang).exists() else PROJECT_RULE_HEADINGS[lang])
                   for lang in LANGS}
    else:
        directory = user_rules_dir()
        current = {lang: rules_file(lang).read_text(encoding="utf-8") for lang in LANGS}
    agent = select_agent(args.agent)
    prompt = (KIT / "prompts" / "add-rule.md").read_text(encoding="utf-8").replace("{{RULE}}", args.rule.strip())
    prompt += "".join(f"=== {lang}.md ===\n{text.rstrip()}\n\n"
                      for lang, text in current.items()) + "=== end ===\n"
    log(f"{agent}: writing the rule (this can take a minute)...")
    new = parse_rules_answer(ask_agent(agent, prompt), current)
    changed = [lang for lang in LANGS if new[lang] != current[lang]]
    if not changed:
        log("the agent changed nothing; the rule may already be covered")
        return 0
    for lang in changed:
        sys.stdout.writelines(difflib.unified_diff(
            current[lang].splitlines(True), new[lang].splitlines(True),
            f"a/{lang}.md", f"b/{lang}.md"))
    if args.dry_run:
        return 0
    if scope == "project":
        seed_project_rules(repo)
    else:
        seed_rules()
    for lang in changed:
        (directory / f"{lang}.md").write_text(new[lang], encoding="utf-8")
        log(f"rules: updated {directory / f'{lang}.md'}")
    if scope == "project":
        log(f"apply it with: `agent-kit init {repo} --agent none`")
    else:
        log("apply it to your repos: `agent-kit sync ~/repos --check`, then without --check")
    return 0


def run(args):
    scope = getattr(args, "scope", "global")
    repo_arg = getattr(args, "repo", None)
    if repo_arg and scope != "project":
        raise InitError("--repo requires --scope project")
    if scope == "project":
        repo = git_root(Path(repo_arg or ".").expanduser().resolve())
        created = seed_project_rules(repo) if getattr(args, "rules_command", None) == "init" else []
        print("Global baseline:")
        for lang in LANGS:
            path = rules_file(lang)
            print(f"  {lang}: {path} ({'bundled' if path.parent == KIT / 'rules' else 'user'})")
        print("Project overlay:")
        for lang in LANGS:
            path = project_rules_file(repo, lang)
            print(f"  {lang}: {path} ({'project' if path.exists() else 'not created'})")
        if created:
            log("project rule overlays created")
            log(f"apply them with: `agent-kit init {repo} --agent none`")
    else:
        if getattr(args, "rules_command", None) == "init":
            seed_rules()
        print(f"user rules dir: {user_rules_dir()}")
        for lang in LANGS:
            path = rules_file(lang)
            print(f"{lang}: {path} ({'bundled' if path.parent == KIT / 'rules' else 'user'})")
    return 0


def add_arguments(parser):
    parser.add_argument("rule", help="the rule, in any language")
    parser.add_argument("--agent", choices=["auto", "claude", "codex"], default="auto")
    parser.add_argument("--scope", choices=["global", "project"], default="global",
                        help="global personal baseline (default) or tracked project overlay")
    parser.add_argument("--repo", help="target repository; requires --scope project")
    parser.add_argument("--dry-run", action="store_true", help="print the diff, write nothing")
    parser.set_defaults(func=run_add)


def register(subparsers):
    parser = subparsers.add_parser("rules", help="show which rules files the managed block is built from")
    commands = parser.add_subparsers(dest="rules_command", required=True)
    show = commands.add_parser("show", help="show the active rule files")
    show.add_argument("--scope", choices=["global", "project"], default="global")
    show.add_argument("--repo", help="target repository; requires --scope project")
    show.set_defaults(func=run)
    initialize = commands.add_parser("init", help="seed rule files without overwriting")
    initialize.add_argument("--scope", choices=["global", "project"], default="global")
    initialize.add_argument("--repo", help="target repository; requires --scope project")
    initialize.set_defaults(func=run)
    add = commands.add_parser("add", help="have a local agent add a rule in every language")
    add_arguments(add)
