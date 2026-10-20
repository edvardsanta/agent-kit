"""Language-aware global and project rules."""

import os
import re
import shutil
from pathlib import Path

from . import KIT, InitError, log
from .git import commit_subjects

END = "<!-- agent-kit:end -->"
START_RE = re.compile(r"<!-- agent-kit:start(?P<attrs>(?: [\w-]+=[\w-]+)*) -->")
MARKER_RE = re.compile(r"<!--\s*(agent-kit|ai-memory):")
LANGS = {"pt": "português do Brasil", "en": "English"}
PROJECT_RULE_HEADINGS = {"en": "## Project rules\n", "pt": "## Regras do projeto\n"}

# Words that are frequent in one language and rare in the other, including common commit verbs.
# Words shared by both (a, as, no, use, remove...) are left out on purpose.
STOPWORDS = {
    "pt": set("""
        de do da dos das e o os um uma que não nao para com em na nas nos pelo pela por mais como
        se é são ao aos seu sua este esta isso isto também quando sem já ou foi ser está estão
        adiciona adicionar corrige corrigir atualiza atualizar cria criar melhora melhorar ajusta
        ajustar mover renomeia documenta implementa permite usando sobre entre
    """.split()),
    "en": set("""
        the and of to is are for with this that it be on from by you your an in or not can will
        how what when which into than then there these those add adds added fix fixes fixed
        update updates updated make support improve rename refactor document allow using about
    """.split()),
}
PT_LETTERS = set("ãõçáéíóúâêôà")
MIN_HITS = 5
DOC_GLOBS = ("README*.md", "CONTRIBUTING*.md", "AGENTS.md", "docs/**/*.md")
MAX_DOC_FILES = 20
MAX_DOC_CHARS = 20000
CODE_RE = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]*`|<!--.*?-->|https?://\S+", re.S)
# managed blocks are generated English/Portuguese boilerplate, not the project's own prose
MANAGED_BLOCK_RE = re.compile(START_RE.pattern + r".*?" + re.escape(END)
                              + r"|<!-- ai-memory:start -->.*?<!-- ai-memory:end -->", re.S)
COMMIT_PREFIX_RE = re.compile(r"^\w+(\([^)]*\))?!?:\s*")


def classify_language(text):
    """Return "pt" or "en" when the text clearly leans one way, else None."""
    hits = dict.fromkeys(STOPWORDS, 0)
    for word in re.findall(r"[^\W\d_]+", CODE_RE.sub(" ", text).lower()):
        for lang, words in STOPWORDS.items():
            if word in words:
                hits[lang] += 1
        if PT_LETTERS.intersection(word) and word not in STOPWORDS["pt"]:
            hits["pt"] += 1
    if hits["pt"] + hits["en"] < MIN_HITS:
        return None
    if hits["pt"] >= 2 * hits["en"]:
        return "pt"
    if hits["en"] >= 2 * hits["pt"]:
        return "en"
    return None


def detect_docs_language(repo):
    paths = []
    for pattern in DOC_GLOBS:
        paths += [p for p in sorted(repo.glob(pattern)) if p.is_file() and p not in paths]
    texts = []
    for path in paths[:MAX_DOC_FILES]:
        text = path.read_text(encoding="utf-8", errors="replace")[:MAX_DOC_CHARS]
        texts.append(MANAGED_BLOCK_RE.sub(" ", text))
    return classify_language("\n".join(texts))


def detect_git_language(repo):
    return classify_language("\n".join(COMMIT_PREFIX_RE.sub("", s) for s in commit_subjects(repo)))


def resolve_docs_language(repo, docs_lang=None):
    """Documentation language only, for commands that do not write Git rules."""
    docs_lang = docs_lang or saved_languages(repo)[0] or detect_docs_language(repo)
    docs_lang = docs_lang or detect_git_language(repo)
    if not docs_lang:
        raise InitError("could not detect the documentation language from README/docs or commits; "
                        "pass --docs-lang pt|en")
    return docs_lang


def resolve_languages(repo, docs_lang=None, git_lang=None, chat_lang=None):
    """Pick each language from the flag, then the saved marker, then the repository itself.

    Chat has no detection: when neither given nor saved it stays None and the rule is omitted.
    """
    saved_docs, saved_chat, saved_git = saved_languages(repo)
    docs_lang = docs_lang or saved_docs
    git_lang = git_lang or saved_git
    if not docs_lang:
        docs_lang = detect_docs_language(repo)
        if docs_lang:
            log(f"detected documentation language: {docs_lang} (from Markdown docs)")
    if not git_lang:
        git_lang = detect_git_language(repo)
        if git_lang:
            log(f"detected Git language: {git_lang} (from commit subjects)")
    docs_lang = docs_lang or git_lang
    git_lang = git_lang or docs_lang
    if not docs_lang:
        raise InitError("could not detect the documentation or Git language from README/docs or "
                        "commits; pass --docs-lang pt|en (and --git-lang if commits differ)")
    return docs_lang, chat_lang or saved_chat, git_lang


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
    if not chat_lang:
        # no chat language chosen: leave it to the user's agent instead of pinning one
        body = "".join(line for line in body.splitlines(keepends=True)
                       if "{{CHAT_LANG_NAME}}" not in line)
    if chat_lang and chat_lang != docs_lang and not supports_split:
        raise InitError(
            f"{rules_file(docs_lang)} uses the old language template; add "
            "{{CHAT_LANG_NAME}} and {{DOCS_LANG_NAME}} before choosing different chat and docs languages")
    replacements = {
        "{{LANG_NAME}}": LANGS[docs_lang],
        "{{DOCS_LANG_NAME}}": LANGS[docs_lang],
        "{{GIT_LANG_NAME}}": LANGS[git_lang],
    }
    if chat_lang:
        replacements["{{CHAT_LANG_NAME}}"] = LANGS[chat_lang]
    for placeholder, value in replacements.items():
        body = body.replace(placeholder, value)
    chat_attr = f" chat-lang={chat_lang}" if chat_lang else ""
    marker = f"<!-- agent-kit:start docs-lang={docs_lang}{chat_attr} git-lang={git_lang} -->"
    return f"{marker}\n{body.rstrip()}\n{END}\n"


def saved_languages(repo):
    path = repo / "AGENTS.md"
    match = START_RE.search(path.read_text()) if path.exists() else None
    if not match:
        return None, None, None
    attrs = dict(re.findall(r"([\w-]+)=([\w-]+)", match.group("attrs")))
    docs_lang = attrs.get("docs-lang") or attrs.get("lang")
    chat_lang = attrs.get("chat-lang")
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
