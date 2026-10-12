# agent-kit

Personal CLI to standardize `AGENTS.md` / `CLAUDE.md` across projects.

## Install

```bash
make install   # symlinks bin/agent-init into ~/.local/bin (PREFIX=... to change)
make test      # stdlib unittest, no dependencies
```

## Usage

```bash
agent-init ~/repos/my-project --lang pt             # conversation/docs in pt, commits in pt
agent-init . --lang pt --git-lang en                # docs in pt, commits/issues/PRs in English
agent-init . --agent codex                          # codex fills the project sections
agent-init . --agent none                           # deterministic part only
agent-init . --migrate-claude                       # old CLAUDE.md -> AGENTS.md + stub
agent-init ~/repos/rpcs3 --hide-agent-files         # fork/upstream: nothing shows up in the diff
agent-init . --dry-run                              # print the diff, write nothing
agent-init . --check                                # exit 1 if anything is outdated
agent-init ~/repos --all --check                    # list outdated agent-kit repos
agent-init ~/repos --all                            # re-apply the rules to all of them
```

## What it does

1. Inserts/updates the `<!-- agent-kit:start -->` block in `AGENTS.md` (rules in `rules/pt.md`, `rules/en.md`):
   language, no co-authorship, commit by batch, worktrees in `.worktrees/`, ai-memory usage.
2. `CLAUDE.md` becomes just `@AGENTS.md`.
3. `.worktrees/` goes into `.git/info/exclude` (use `--tracked` for the versioned `.gitignore`).
4. `.claude/settings.local.json` with empty `attribution` (turns off Claude Code's Co-Authored-By).
5. `ai-memory install-instructions` (routing block + skills; `--no-skills`, `--full-memory`).
6. An agent (`claude -p` or `codex exec`) reads the repo and writes overview, commands, conventions and
   pitfalls outside the managed blocks (`prompts/fill.md`).

Idempotent: the language is stored in the marker, so running it again does not change the language.
It never commits.

`--migrate-claude` needs an agent (it refuses `--agent none`), and `CLAUDE.md` is only replaced
by the stub if the agent exits cleanly.

## Changing a rule for every project

Edit `rules/*.md`, then:

```bash
agent-init ~/repos --all --check   # see which repos are outdated
agent-init ~/repos --all --dry-run # see the diff
agent-init ~/repos --all           # apply
```

`--all` scans up to 3 levels below the given directory and only touches repos whose `AGENTS.md`
already has the agent-kit marker. It runs the deterministic part only (steps 1-4: no ai-memory,
no agent) and keeps each repo's saved languages, so it does not accept `--lang` or other per-repo
flags. Repos with an old marker without a saved language are skipped; run
`agent-init <repo> --lang <pt|en>` there once.
