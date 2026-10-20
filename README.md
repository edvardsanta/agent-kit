# agent-kit

Personal CLI to standardize `AGENTS.md` / `CLAUDE.md` across projects.

## Install

```bash
make install          # symlinks agent-kit and agent-init into ~/.local/bin
make test             # stdlib unittest, no dependencies
agent-kit doctor      # show which optional tools are available
agent-kit --version
```

`agent-init` is an alias for `agent-kit init`. Use `agent-kit` for the other subcommands.

## Usage

```bash
agent-init . --profile own                          # your repo: track .worktrees/ in .gitignore
agent-init ~/repos/rpcs3 --profile upstream         # third-party clone: hide local artifacts
agent-init . --chat-lang pt --docs-lang en --git-lang en
agent-init . --agent codex                          # choose explicitly; default is auto
agent-init . --agent none                           # deterministic part only
agent-init . --trust                                # your own repo: agent loads its hooks/MCP (ai-memory)
agent-init . --migrate-claude                       # old CLAUDE.md -> AGENTS.md + stub
agent-init . --keep-claude                          # intentionally keep an independent CLAUDE.md
agent-init . --dry-run                              # print the diff, write nothing
agent-init . --check                                # exit 1 if anything is outdated
agent-kit sync ~/repos --check                      # list repos needing an update/migration
agent-kit sync ~/repos                              # re-apply rules to all managed repos
agent-kit procedures init                           # create shared project procedures
```

`--lang` remains as a compatibility alias for `--chat-lang` plus `--docs-lang`.
`init --all`, `--hide-agent-files`, `rules --init`, and `add-rule` also remain supported.
The upstream profile refuses to modify an already tracked `AGENTS.md`, `CLAUDE.md`, or generated
Claude settings because `.git/info/exclude` cannot hide changes to tracked files.

## What it does

1. Inserts/updates the `<!-- agent-kit:start -->` block in `AGENTS.md` (rules in `rules/pt.md`, `rules/en.md`):
   language, no co-authorship, commit by batch, worktrees, project procedures and ai-memory usage.
2. `CLAUDE.md` becomes just `@AGENTS.md`.
3. `.worktrees/` goes into `.git/info/exclude` (use `--tracked` for the versioned `.gitignore`).
4. `.claude/settings.local.json` with empty `attribution` (turns off Claude Code's Co-Authored-By).
5. `ai-memory install-instructions` (routing block + skills; `--no-skills`, `--full-memory`).
6. An agent (`claude -p` or `codex exec`) reads the repo and answers with overview, commands,
   conventions and pitfalls (`prompts/fill.md`); agent-kit writes them outside the managed blocks.

Idempotent: chat, documentation, and Git languages are stored independently in the marker, so
running it again preserves each choice. The command can be run from any repository subdirectory.
It never commits.

`--migrate-claude` needs an agent (it refuses `--agent none`), and `CLAUDE.md` is only replaced
by the stub if the agent exits cleanly. An independent `CLAUDE.md` otherwise stops initialization
before any write; use `--keep-claude` to keep it intentionally.

Agent output is generated and validated before planned repository changes are applied. A missing
agent or rejected answer therefore leaves the repository unchanged. `--agent auto` chooses Claude,
then Codex, and explains how to continue with `--agent none` when neither is installed.

## Prompt injection

The agent in step 6 reads files you did not write (READMEs, code, an old `CLAUDE.md`), and what
it produces becomes instructions for every agent that later works in that repo. So:

- **The agent cannot write.** claude gets only Read/Glob/Grep and `git log` / `git ls-files` /
  `ls`; codex runs with `--sandbox read-only`. It prints the sections; agent-kit validates them
  (delimiters, a `## ` heading, no managed-block markers) and writes only the project part of
  `AGENTS.md`. A rejected answer leaves every file as it was.
- **The target repo's Claude Code config is ignored**: `--setting-sources user --strict-mcp-config`,
  so a cloned repo's `.claude/settings.json` hooks and `.mcp.json` servers never run. Pass
  `--trust` for your own repos to load them (for example ai-memory); the agent still cannot write.
- **The prompt treats repo content as data**, not instructions, and forbids copying remote-code,
  `sudo`, permission or hook commands that are not in a manifest, Makefile or CI.
- **Suspicious added lines are flagged** under `REVIEW:` (URLs, `curl`/`wget`/`sudo`, `| sh`,
  hooks, permissions, tokens, "ignore previous..."). The diff is always printed, and nothing is committed.

This reduces the risk; it does not remove it. Read the `AGENTS.md` diff before committing, especially
in repos you cloned from someone else. `sync`, `--all`, `--check` and `--dry-run` never call an
agent. Rule editing runs the agent with no tools in an empty directory.

## Your rules

The bundled `rules/` are defaults. Your own rules live outside the checkout, so `git pull`
never conflicts with them:

- the user rules dir is `$AGENT_KIT_RULES` if set, else `~/.config/agent-kit/rules`
  (`$XDG_CONFIG_HOME` is respected);
- `<lang>.md` is read from there, and a language missing there falls back to the bundled
  `rules/<lang>.md`.

```bash
agent-kit rules show          # show global rule files
agent-kit rules init          # seed global personal rules (never overwrites)
agent-kit rules add "never git push without asking"
```

Both files have `{{CHAT_LANG_NAME}}`, `{{DOCS_LANG_NAME}}`, and `{{GIT_LANG_NAME}}`
placeholders, and they should say the same thing in each language. Existing personal templates
using the legacy `{{LANG_NAME}}` placeholder continue to work when chat and docs use one language.

### Project-specific rules

Project rules are tracked additive overlays in `.agent-kit/rules/{en,pt}.md`. They are appended
to the global baseline instead of copying it, so later global updates still propagate.

```bash
agent-kit rules init --scope project
agent-kit rules add "never force-push" --scope project
agent-kit rules show --scope project           # shows baseline plus overlay
agent-kit init . --agent none                  # render the updated AGENTS.md block
```

Pass `--repo PATH` to manage another repository. The local Claude or Codex CLI gets the current
rules and returns every language file
with the rule placed in the right section, translated, and merged with any rule it overlaps.
It runs with no tools in an empty directory. agent-kit checks the answer (every language present,
placeholders and first heading kept) before writing to your rules dir, and prints the diff.

Global rule editing remains available through `agent-kit rules add "..."`; `agent-kit add-rule`
is its compatibility alias.

## Project procedures

Reusable workflows belong to the project rather than to Claude, Codex or a temporary scratchpad.
agent-kit uses the tracked `.agent-kit/procedures/` directory so every user and agent sees the
same procedures while agent-specific configuration remains separate.

```bash
agent-kit procedures init              # create README.md without overwriting it later
agent-kit procedures add release       # create release.md from a safe template
agent-kit procedures path              # print the absolute directory path
agent-kit procedures list              # list Markdown procedures
agent-kit procedures show release      # print release.md
```

`procedures init` uses the repository's saved documentation language, supports `--check` and
`--dry-run`, and can run from any repository subdirectory. `procedures add` initializes the
directory when needed, supports nested names and `--title`, and never overwrites an existing file.
Keep one workflow per Markdown file.
Temporary directories remain appropriate for disposable investigation artifacts; create or update
a durable procedure only when the user explicitly asks to preserve it.

## Changing a rule for every project

Edit your rules (or use `add-rule`), then:

```bash
agent-kit sync ~/repos --check   # see outdated repos and required migrations
agent-kit sync ~/repos --dry-run # see the diff
agent-kit sync ~/repos           # apply
```

`sync` scans up to 3 levels below the given directory and only touches repos whose `AGENTS.md`
already has the agent-kit marker. It runs the deterministic part only (steps 1-4: no ai-memory,
no agent) and keeps each repo's saved languages. Repositories requiring migration are counted in
the summary, and make `--check` exit 1 instead of reporting everything as current. Repos with an
old marker without a saved language need one explicit initialization:
`agent-kit init <repo> --docs-lang <pt|en> --agent none`.

## License

MIT, see [LICENSE](LICENSE).
