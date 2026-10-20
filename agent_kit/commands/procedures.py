"""Manage reusable, AI-authored project procedures."""

import re
import sys
import unicodedata
from pathlib import Path

from .. import KIT, InitError, log
from ..agents import ask_repo_agent, select_agent
from ..changes import Changes
from ..git import git_root
from ..languages import LANGS, MARKER_RE, saved_languages
from .init import suspicious_lines

PROCEDURES_README = {
    "en": """# Project procedures

Reusable project workflows shared by users and all agents.

- Keep one procedure per Markdown file.
- Record prerequisites, ordered steps, verification and rollback where relevant.
- Do not store secrets, credentials or disposable scratch work here.
- Create or update procedures only when the user explicitly asks to preserve them.
""",
    "pt": """# Procedimentos do projeto

Fluxos reutilizáveis do projeto, compartilhados por usuários e todos os agentes.

- Mantenha um procedimento por arquivo Markdown.
- Registre pré-requisitos, passos ordenados, verificação e reversão quando relevante.
- Não guarde segredos, credenciais nem rascunhos descartáveis aqui.
- Crie ou atualize procedimentos somente quando o usuário pedir explicitamente para preservá-los.
""",
}

DESCRIPTION_PROMPTS = {
    "en": (
        "Explain the procedure for the AI. Describe its goal, when to use it, and important "
        "constraints. Finish with an empty line."
    ),
    "pt": (
        "Explique o procedimento para a IA. Descreva o objetivo, quando usá-lo e restrições "
        "importantes. Termine com uma linha vazia."
    ),
}


def procedures_dir(repo):
    directory = repo / ".agent-kit" / "procedures"
    try:
        directory.resolve().relative_to(repo.resolve())
    except ValueError:
        raise InitError(f"{directory} resolves outside the repository")
    return directory


def slugify(value):
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def normalized_procedure_name(name):
    raw = Path(name)
    if raw.is_absolute() or any(part in ("", ".", "..") for part in raw.parts):
        raise InitError("procedure names must be relative and cannot leave .agent-kit/procedures")
    if raw.suffix and raw.suffix.lower() != ".md":
        raise InitError("procedures must be Markdown files")
    source_parts = list(raw.parts)
    source_parts[-1] = Path(source_parts[-1]).stem
    parts = [slugify(part) for part in source_parts]
    if any(not part for part in parts):
        raise InitError("procedure name must contain letters or numbers")
    return Path(*parts).with_suffix(".md")


def procedure_path(directory, name, normalize=False):
    relative = normalized_procedure_name(name) if normalize else Path(name)
    if relative.name in ("", ".", ".."):
        raise InitError("procedure name must identify a Markdown file")
    if relative.suffix == "":
        relative = relative.with_suffix(".md")
    elif relative.suffix.lower() != ".md":
        raise InitError("procedures must be Markdown files")
    if relative.is_absolute():
        raise InitError("procedure names must be relative to .agent-kit/procedures")
    candidate = (directory / relative).resolve()
    try:
        candidate.relative_to(directory.resolve())
    except ValueError:
        raise InitError("procedure names cannot leave .agent-kit/procedures")
    return candidate


def prompt_for_description(lang, input_fn=None):
    input_fn = input_fn or input
    print(DESCRIPTION_PROMPTS[lang], file=sys.stderr)
    lines = []
    while True:
        try:
            print("> " if not lines else "| ", end="", file=sys.stderr, flush=True)
            line = input_fn("")
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line.strip())
    description = "\n".join(lines).strip()
    if not description:
        raise InitError("procedure description cannot be empty")
    return description


def resolve_description(description, lang):
    if description and description.strip():
        return description.strip()
    if not sys.stdin.isatty():
        raise InitError("--description is required when input is not interactive")
    return prompt_for_description(lang)


def parse_procedure(answer, expected_title=None):
    match = re.search(r"^=== procedure ===[ \t]*$(.*?)^=== end ===", answer,
                      flags=re.M | re.S)
    if not match:
        raise InitError("agent answer lacks the `=== procedure ===` / `=== end ===` delimiters; nothing written")
    body = match.group(1).strip("\n")
    if MARKER_RE.search(body):
        raise InitError("agent answer contains managed-block markers; nothing written")
    lines = body.splitlines()
    if not lines or not re.fullmatch(r"# [^#\n]+", lines[0]):
        raise InitError("agent answer must start with a single level-one title; nothing written")
    title = lines[0][2:].strip()
    if expected_title and title != expected_title:
        raise InitError(f"agent answer must start with `# {expected_title}`; nothing written")
    if not any(line.startswith("## ") for line in lines):
        raise InitError("agent answer has no procedure sections; nothing written")
    return title, body.rstrip() + "\n"


def generate_procedure(repo, agent, path, title, description, lang, trust):
    relative = path.relative_to(repo).as_posix() if path else None
    prompt = (KIT / "prompts" / "add-procedure.md").read_text()
    replacements = {
        "{{PATH}}": f"`{relative}`" if relative else "derive a concise kebab-case filename from the procedure",
        "{{TITLE}}": f"`{title}`" if title else "derive a concise title from the user's explanation",
        "{{DESCRIPTION}}": description,
        "{{LANG_NAME}}": LANGS[lang],
        "{{TITLE_RULE}}": (f"Start with a single `# {title}` heading."
                           if title else "Choose a concise title and start with it as a single `# ` heading."),
    }
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)
    target = relative or "from the user's explanation"
    answer = ask_repo_agent(repo, agent, prompt, trust, f"writing procedure {target}")
    return parse_procedure(answer, title)


def run(args):
    repo = git_root(Path(args.repo).expanduser().resolve())
    directory = procedures_dir(repo)
    command = args.procedures_command
    if command == "path":
        print(directory)
        return 0
    if command == "init":
        docs_lang, _, _ = saved_languages(repo)
        lang = args.docs_lang or docs_lang or "pt"
        readme = directory / "README.md"
        changes = Changes(repo)
        if not readme.exists():
            changes.write(readme, PROCEDURES_README[lang],
                          "procedures: created .agent-kit/procedures/README.md")
        if args.check:
            if changes.pending:
                log("procedures not initialized")
                return 1
            log("procedures initialized")
            return 0
        if args.dry_run:
            changes.diff()
            return 0
        if not changes.pending:
            log("procedures already initialized")
            return 0
        changes.apply()
        log("add Markdown procedure files to .agent-kit/procedures/ and commit them with the project")
        return 0
    if command == "add":
        docs_lang, _, _ = saved_languages(repo)
        lang = args.docs_lang or docs_lang or "pt"
        if not args.name and not sys.stdin.isatty():
            raise InitError("procedure name is required when input is not interactive")
        path = procedure_path(directory, args.name, normalize=True) if args.name else None
        if path and path.name.lower() == "readme.md":
            raise InitError("README.md is reserved for the procedures index")
        if path and path.exists():
            relative = path.relative_to(directory.resolve())
            raise InitError(f"procedure already exists: {relative}")
        title = args.title
        if not title and args.name:
            title = Path(args.name).stem.replace("-", " ").replace("_", " ").strip().title()
        if title and ("\n" in title or "\r" in title or MARKER_RE.search(title)):
            raise InitError("procedure title must be a single plain-text line")
        description = resolve_description(args.description, lang)
        agent = select_agent(args.agent)
        generated_title, procedure = generate_procedure(
            repo, agent, path, title, description, lang, args.trust)
        if path is None:
            path = procedure_path(directory, generated_title, normalize=True)
            if path.name.lower() == "readme.md":
                raise InitError("the generated README.md name is reserved for the procedures index")
            if path.exists():
                relative = path.relative_to(directory.resolve())
                raise InitError(f"procedure already exists: {relative}")
        changes = Changes(repo)
        readme = directory / "README.md"
        if not readme.exists():
            changes.write(readme, PROCEDURES_README[lang],
                          "procedures: created .agent-kit/procedures/README.md")
        changes.write(path, procedure, f"procedures: created {changes.rel(path)}")
        changes.diff()
        if args.dry_run:
            return 0
        changes.apply()
        flagged = suspicious_lines("", procedure)
        if flagged:
            log("REVIEW: the procedure contains commands, URLs, permissions, or sensitive terms:")
            for line in flagged:
                log(f"  | {line.strip()}")
        log(f"review {changes.rel(path)}, then commit it with the project")
        return 0
    if not directory.is_dir():
        raise InitError("project procedures are not initialized; run `agent-kit procedures init`")
    if command == "list":
        files = sorted(path.relative_to(directory) for path in directory.rglob("*.md")
                       if path.name != "README.md")
        if not files:
            log("no project procedures found")
            return 0
        for path in files:
            print(path.as_posix())
        return 0
    path = procedure_path(directory, args.name)
    if not path.is_file():
        raise InitError(f"procedure not found: {args.name}")
    text = path.read_text()
    print(text, end="" if text.endswith("\n") else "\n")
    return 0


def register(subparsers):
    parser = subparsers.add_parser("procedures", help="manage AI-agnostic procedures stored with the project")
    commands = parser.add_subparsers(dest="procedures_command", required=True)
    path = commands.add_parser("path", help="print the project procedures directory")
    path.add_argument("--repo", default=".", help="target repository")
    path.set_defaults(func=run)
    initialize = commands.add_parser("init", help="create the project procedures directory")
    initialize.add_argument("--repo", default=".", help="target repository")
    initialize.add_argument("--docs-lang", choices=LANGS,
                            help="README language (default: saved docs language, else pt)")
    output = initialize.add_mutually_exclusive_group()
    output.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 if procedures are not initialized")
    output.add_argument("--dry-run", action="store_true", help="write nothing; print the README diff")
    initialize.set_defaults(func=run)
    add = commands.add_parser("add", help="have a local agent write a project procedure")
    add.add_argument("name", nargs="?",
                     help="optional name or path; omit it to derive both title and filename interactively")
    add.add_argument("--repo", default=".", help="target repository")
    add.add_argument("--title", help="document title (default: derived from the name or by the AI)")
    add.add_argument("--description",
                     help="what the procedure should accomplish (prompted in terminals; required in scripts)")
    add.add_argument("--docs-lang", choices=LANGS,
                     help="procedure language (default: saved docs language, else pt)")
    add.add_argument("--agent", choices=["auto", "claude", "codex"], default="auto",
                     help="local agent CLI to use (default: auto, Claude then Codex)")
    add.add_argument("--trust", action="store_true",
                     help="allow the agent to load the target repo's Claude config and MCP servers")
    add.add_argument("--dry-run", action="store_true",
                     help="call the agent and print the resulting diff without writing")
    add.set_defaults(func=run)
    listing = commands.add_parser("list", help="list project procedure files")
    listing.add_argument("--repo", default=".", help="target repository")
    listing.set_defaults(func=run)
    show = commands.add_parser("show", help="print a project procedure")
    show.add_argument("name", help="procedure name or relative Markdown path")
    show.add_argument("--repo", default=".", help="target repository")
    show.set_defaults(func=run)
