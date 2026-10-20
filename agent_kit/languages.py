"""Language-aware global and project rules."""

import os
import re
import shutil
from pathlib import Path

from . import KIT, InitError, log

END = "<!-- agent-kit:end -->"
START_RE = re.compile(r"<!-- agent-kit:start(?P<attrs>(?: [\w-]+=[\w-]+)*) -->")
MARKER_RE = re.compile(r"<!--\s*(agent-kit|ai-memory):")
LANGS = {"pt": "português do Brasil", "en": "English"}
PROJECT_RULE_HEADINGS = {"en": "## Project rules\n", "pt": "## Regras do projeto\n"}


def user_rules_dir():
    configured = os.environ.get("AGENT_KIT_RULES")
    if configured:
        return Path(configured).expanduser()
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "agent-kit" / "rules"


def rules_file(lang):
    path = user_rules_dir() / f"{lang}.md"
    return path if path.exists() else KIT / "rules" / f"{lang}.md"


def project_rules_file(repo, lang):
    return repo / ".agent-kit" / "rules" / f"{lang}.md"


def seed_rules():
    directory = user_rules_dir()
    for lang in LANGS:
        path = directory / f"{lang}.md"
        if not path.exists():
            directory.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(KIT / "rules" / f"{lang}.md", path)
            log(f"rules: created {path}")


def seed_project_rules(repo):
    created = []
    for lang, heading in PROJECT_RULE_HEADINGS.items():
        path = project_rules_file(repo, lang)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(heading)
            log(f"rules: created {path}")
            created.append(path)
    return created


def render_block(docs_lang, git_lang, chat_lang=None, repo=None):
    chat_lang = chat_lang or docs_lang
    body = rules_file(docs_lang).read_text()
    supports_split = "{{CHAT_LANG_NAME}}" in body and "{{DOCS_LANG_NAME}}" in body
    if repo:
        project_file = project_rules_file(repo, docs_lang)
        if project_file.exists():
            project_body = project_file.read_text().strip()
            if MARKER_RE.search(project_body):
                raise InitError(f"{project_file}: managed-block markers are not allowed in project rules")
            if project_body:
                body = body.rstrip() + "\n\n" + project_body + "\n"
    if chat_lang != docs_lang and not supports_split:
        raise InitError(
            f"{rules_file(docs_lang)} uses the old language template; add "
            "{{CHAT_LANG_NAME}} and {{DOCS_LANG_NAME}} before choosing different chat and docs languages")
    replacements = {
        "{{LANG_NAME}}": LANGS[docs_lang],
        "{{CHAT_LANG_NAME}}": LANGS[chat_lang],
        "{{DOCS_LANG_NAME}}": LANGS[docs_lang],
        "{{GIT_LANG_NAME}}": LANGS[git_lang],
    }
    for placeholder, value in replacements.items():
        body = body.replace(placeholder, value)
    marker = f"<!-- agent-kit:start docs-lang={docs_lang} chat-lang={chat_lang} git-lang={git_lang} -->"
    return f"{marker}\n{body.rstrip()}\n{END}\n"


def saved_languages(repo):
    path = repo / "AGENTS.md"
    match = START_RE.search(path.read_text()) if path.exists() else None
    if not match:
        return None, None, None
    attrs = dict(re.findall(r"([\w-]+)=([\w-]+)", match.group("attrs")))
    docs_lang = attrs.get("docs-lang") or attrs.get("lang")
    chat_lang = attrs.get("chat-lang") or attrs.get("lang")
    return docs_lang, chat_lang, attrs.get("git-lang")


def saved_langs(repo):
    docs_lang, _, git_lang = saved_languages(repo)
    return docs_lang, git_lang


def has_marker(repo):
    path = repo / "AGENTS.md"
    return path.exists() and START_RE.search(path.read_text()) is not None


def upsert_block(text, block):
    if text is None:
        return f"# AGENTS.md\n\n{block}"
    pattern = re.compile(START_RE.pattern + r".*?" + re.escape(END) + r"\n?", re.S)
    if pattern.search(text):
        return pattern.sub(lambda _: block, text, count=1)
    match = re.match(r"(#[^\n]*\n+)", text)
    head, rest = (match.group(1), text[match.end():]) if match else ("", text)
    return f"{head}{block}\n{rest}"
