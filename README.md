# agent-kit

Personal CLI to standardize `AGENTS.md` / `CLAUDE.md` across projects.

The first-release command surface and behavioral guarantees are documented in
[`docs/cli-contract.md`](docs/cli-contract.md). If you used an earlier development checkout, see
the [`0.1 migration notes`](docs/migration-0.1.md).

## Install

Requirements: Python 3.10+ and `git` on `PATH`. There are no other runtime dependencies.
`claude`, `codex` and `ai-memory` are optional; `agent-kit doctor` shows which ones it finds.

Linux and macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/edvardsanta/agent-kit/main/install.sh | sh
```

Windows (PowerShell; requires [Git for Windows](https://git-scm.com/download/win)):

```powershell
irm https://raw.githubusercontent.com/edvardsanta/agent-kit/main/install.ps1 | iex
```

The installers check Python and `git`, install the most recent release
([`v0.1.5.dev0`](https://github.com/edvardsanta/agent-kit/releases/tag/v0.1.5.dev0) today), and
use `uv tool` or `pipx` when available, else a private virtualenv under
`~/.local/share/agent-kit` (Windows: `%LOCALAPPDATA%\agent-kit`, whose `bin` is added to the user
`PATH`). To upgrade later, run `agent-kit upgrade` (or the same install command again). Set
`AGENT_KIT_VERSION=<tag>` to pin a release, or `AGENT_KIT_INSTALLER=uv|pipx|venv` to choose the
method.

Then check the installation:

```bash
agent-kit --version
agent-kit doctor
```

If you prefer to install it yourself, any Python tool installer works with the tag URL:
`pipx install git+https://github.com/edvardsanta/agent-kit@v0.1.5.dev0` (or `uv tool install`).
`agent-kit upgrade` installs the latest release (`--version <tag>` picks one) with the same tool
that installed it, then runs `agent-kit sync --known` with the new version so your repositories get
its changes (`--no-sync` skips that). To remove it, run `agent-kit uninstall` (add `--purge` to also delete your
personal rules). Both work for the installers, `uv tool` and `pipx`; for anything else, use the
tool you installed with.

`agent-init` is an alias for `agent-kit init`; use `agent-kit` for the other subcommands. The
installed package includes its bundled rules and prompts, so it does not depend on a source
checkout.

### From a checkout (development)

```bash
git clone https://github.com/edvardsanta/agent-kit && cd agent-kit
pipx install --editable .       # or: python -m pip install -e .
make install                    # Unix-only alternative: symlinks bin/agent-kit into ~/.local/bin
make test                       # stdlib unittest
```

CI runs the unit suite on Linux and macOS and builds, installs, and smoke-tests the wheel on Linux,
macOS, and Windows with the oldest and newest supported Python versions, and runs both installers
on all three systems. On Windows the unit suite does not run, so agent-backed commands are less
exercised there.

## Usage

```bash
agent-init . --profile own                          # your repo: track .worktrees/ in .gitignore
agent-init ~/repos/rpcs3 --profile upstream         # third-party clone: hide local artifacts
agent-init . --docs-lang en --git-lang en              # override detected languages
agent-init . --chat-lang pt                         # also pin the agent's chat language
agent-init . --agent codex                          # choose explicitly; default is auto
agent-init . --agent none                           # deterministic part only
agent-init . --memory off                           # skip ai-memory integration
agent-init . --memory full                          # install the expanded routing guidance
agent-init . --trust                                # your own repo: agent loads its hooks/MCP (ai-memory)
agent-init . --migrate-claude                       # old CLAUDE.md -> AGENTS.md + stub
agent-init . --keep-claude                          # intentionally keep an independent CLAUDE.md
agent-init . --dry-run                              # print the diff, write nothing
agent-init . --check                                # exit 1 if anything is outdated
agent-kit sync ~/repos --check                      # list repos needing an update/migration
agent-kit sync ~/repos                              # re-apply rules to all managed repos
agent-kit procedures init                           # create shared project procedures
```

The upstream profile refuses to modify an already tracked `AGENTS.md`, `CLAUDE.md`, or generated
Claude settings because `.git/info/exclude` cannot hide changes to tracked files.

## What it does

1. Inserts/updates the `<!-- agent-kit:start -->` block in `AGENTS.md` (rules packaged under
   `agent_kit/rules/`):
   language, no co-authorship, commit by batch, worktrees, project procedures and ai-memory usage.
2. `CLAUDE.md` becomes just `@AGENTS.md`.
3. `.worktrees/` goes into `.git/info/exclude` (use `--tracked` for the versioned `.gitignore`).
4. `.claude/settings.local.json` with empty `attribution` (turns off Claude Code's Co-Authored-By).
5. Agent skills in `.claude/skills/` (Claude Code) and `.agents/skills/` (Codex), so you can stay in
   your agent: `agent-kit-rules` ("from now on, never force-push") has it edit
   `.agent-kit/rules/` and re-render the block with `agent-kit init --agent none`, and
   `agent-kit-procedures` ("save how we release as a procedure") has it write the procedure and
   regenerate the index with `agent-kit procedures init`. They are replaced on every run;
   `--profile upstream` hides them from Git.
6. Unless `--memory off` is selected, `ai-memory install-instructions` installs its routing block
   and skills. The default is `compact`; `--profile upstream` defaults to `off`.
7. An agent (`claude -p` or `codex exec`) reads the repo and answers with overview, commands,
   conventions and pitfalls (`agent_kit/prompts/fill.md`); agent-kit writes them outside the
   managed blocks.

Languages: the documentation language is detected from `README*`, `CONTRIBUTING*`, `AGENTS.md`
and `docs/**/*.md` (code blocks ignored), and the Git language from recent commit subjects. If only
one is detectable it is used for both; if neither is, `init` exits 2 and asks for `--docs-lang`.
The chat language is not detected: without `--chat-lang` the managed block has no chat rule and
your agent's own settings decide.

Idempotent: the chosen languages are stored independently in the marker, so running it again
preserves each choice instead of detecting again. The command can be run from any repository subdirectory.
It never commits.

Requested data and diffs are written to stdout. Progress, warnings, review notices, prompts, and
errors are written to stderr, so commands such as `procedures list`, `procedures show`, and
`procedures path` can be safely piped.

`--migrate-claude` needs an agent (it refuses `--agent none`), and `CLAUDE.md` is only replaced
by the stub if the agent exits cleanly. An independent `CLAUDE.md` otherwise stops initialization
before any write; use `--keep-claude` to keep it intentionally.

Agent output is generated and validated before planned repository changes are applied. A missing
agent or rejected answer therefore leaves the repository unchanged. `--agent auto` uses Claude, then
Codex: if Claude is missing, or fails (not logged in, out of quota, an answer in the wrong format),
it tries Codex and logs why. It explains how to continue with `--agent none` when neither is
installed. An explicit `--agent claude` or `--agent codex` never switches to the other.

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
in repos you cloned from someone else. `sync`, `--check` and deterministic `--dry-run` never call an
agent. Rule editing runs the agent with no tools in an empty directory.

## Your rules

The bundled `agent_kit/rules/` files are defaults. Your own rules live outside the checkout, so `git pull`
never conflicts with them:

- the user rules dir is `$AGENT_KIT_RULES` if set, else `~/.config/agent-kit/rules`
  (`$XDG_CONFIG_HOME` is respected);
- `<lang>.md` is read from there, and a language missing there falls back to the bundled
  `agent_kit/rules/<lang>.md`.

```bash
agent-kit rules show          # show global rule files
agent-kit rules init          # seed global personal rules (never overwrites)
agent-kit rules add "never git push without asking" --scope global
```

Both files have `{{CHAT_LANG_NAME}}`, `{{DOCS_LANG_NAME}}`, and `{{GIT_LANG_NAME}}`
placeholders, and they should say the same thing in each language. Existing personal templates
using the legacy `{{LANG_NAME}}` placeholder continue to work when chat and docs use one language.
Lines with `{{CHAT_LANG_NAME}}` are dropped when no chat language was chosen.

### Project-specific rules

Project rules are tracked additive overlays in `.agent-kit/rules/{en,pt}.md`. They are appended
to the global baseline instead of copying it, so later global updates still propagate. `rules add`
targets them by default: a strict rule rarely makes sense in every repository, so global rules take
`--scope global`.

```bash
agent-kit rules add                            # describe the rule in your own words
agent-kit rules add "never force-push"         # or pass it; both write .agent-kit/rules/
agent-kit rules show --scope project           # shows baseline plus overlay
agent-kit init . --agent none                  # render the updated AGENTS.md block
```

Pass `--repo PATH` to manage another repository. The local Claude or Codex CLI gets the current
rules and returns every language file
with the rule placed in the right section, translated, and merged with any rule it overlaps.
It runs with no tools in an empty directory. agent-kit checks the answer (every language present,
placeholders and first heading kept) before writing the rules files, and prints the diff.

## Project procedures

Reusable workflows belong to the project rather than to Claude, Codex or a temporary scratchpad.
agent-kit uses the tracked `.agent-kit/procedures/` directory so every user and agent sees the
same procedures while agent-specific configuration remains separate.

```bash
agent-kit procedures init              # create README.md without overwriting it later
agent-kit procedures add               # interactive: explain it; AI derives title and filename
agent-kit procedures add --repo ~/src/app  # interactive flow for another repository
agent-kit procedures add deploy --description "deploy production safely"  # scripts
agent-kit procedures path              # print the absolute directory path
agent-kit procedures list              # list Markdown procedures
agent-kit procedures show release      # print release.md
```

`procedures init` uses the repository's saved (else detected) documentation language, supports `--check` and
`--dry-run`, and can run from any repository subdirectory. `procedures add` initializes the
directory when needed, supports nested names, `--title`, `--description`, `--agent` and `--trust`,
and never overwrites an existing file. With no arguments, it starts an interactive multiline flow:
the user explains the goal, context and constraints, then the AI derives the title and safe filename.
When a human-readable name is supplied, it is converted to a safe path, so `"don't use tmp"`
becomes `dont-use-tmp.md`. Scripts and other non-interactive callers must pass both the name and
`--description`. Claude or Codex inspects the repository read-only and
returns the complete procedure; agent-kit validates the delimiters, title, sections and managed
markers before writing it. The target repository's Claude configuration is ignored unless
`--trust` is passed. `--dry-run` still calls the agent, but only prints the resulting diff.
Each generated procedure starts with a one-sentence purpose summary. agent-kit maintains a compact
`INDEX.md` containing titles, relative links and those summaries; `procedures init` safely rebuilds
the index without overwriting the user-owned `README.md`. The managed rules tell agents to consult
the index and load a matching procedure before performing its workflow.
Keep one workflow per Markdown file.
Temporary directories remain appropriate for disposable investigation artifacts; create or update
a durable procedure only when the user explicitly asks to preserve it.

## Code architecture

`bin/agent-kit` is a thin executable entry point. The implementation lives in the `agent_kit`
package: shared change planning, Git, language and agent adapters are separate from command modules
under `agent_kit/commands/`. Each command owns its parser registration and runtime behavior, while
AI subprocess policy is centralized in `agent_kit/agents.py`.

## Changing a rule for every project

Edit your rules (or use `agent-kit rules add`), then:

```bash
agent-kit sync ~/repos --check   # see outdated repos and required migrations
agent-kit sync ~/repos --dry-run # see the diff
agent-kit sync ~/repos           # apply
```

`sync` scans up to 3 levels below the given directory and only touches repos whose `AGENTS.md`
already has the agent-kit marker. It runs the deterministic part only (steps 1-5: no ai-memory,
no agent) and keeps each repo's saved languages. Repositories requiring migration are counted in
the summary, and make `--check` exit 1 instead of reporting everything as current. Repos with an
old marker without a saved language need one explicit initialization:
`agent-kit init <repo> --docs-lang <pt|en> --agent none`.

`init` and `sync` record every repository they set up in `~/.local/state/agent-kit/repos`
(`$XDG_STATE_HOME`, or `$AGENT_KIT_STATE` to move it). `agent-kit sync --known` syncs exactly those,
from any directory, skipping the ones that no longer exist; `agent-kit upgrade` runs it for you.
Repositories set up before this record existed join it the next time you run `agent-kit sync <folder>`
or `agent-init` on them. Repositories initialized with `--profile upstream` keep their agent files
hidden from Git when synced.

## License

MIT, see [LICENSE](LICENSE).
