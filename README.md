# agent-kit

Personal CLI to standardize `AGENTS.md` / `CLAUDE.md` across projects.

## Install

```bash
make install   # symlinks agent-kit and agent-init into ~/.local/bin (PREFIX=... to change)
make test      # stdlib unittest, no dependencies
```

`agent-init` is an alias for `agent-kit init`; every example below works with either.

## Usage

```bash
agent-init ~/repos/my-project --lang pt             # conversation/docs in pt, commits in pt
agent-init . --lang pt --git-lang en                # docs in pt, commits/issues/PRs in English
agent-init . --agent codex                          # codex fills the project sections
agent-init . --agent none                           # deterministic part only
agent-init . --trust                                # your own repo: agent loads its hooks/MCP (ai-memory)
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
6. An agent (`claude -p` or `codex exec`) reads the repo and answers with overview, commands,
   conventions and pitfalls (`prompts/fill.md`); agent-kit writes them outside the managed blocks.

Idempotent: the language is stored in the marker, so running it again does not change the language.
It never commits.

`--migrate-claude` needs an agent (it refuses `--agent none`), and `CLAUDE.md` is only replaced
by the stub if the agent exits cleanly.

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
in repos you cloned from someone else. `--all`, `--check` and `--dry-run` never call an agent.
`add-rule` runs the agent with no tools in an empty directory.

## Your rules

The bundled `rules/` are defaults. Your own rules live outside the checkout, so `git pull`
never conflicts with them:

- the user rules dir is `$AGENT_KIT_RULES` if set, else `~/.config/agent-kit/rules`
  (`$XDG_CONFIG_HOME` is respected);
- `<lang>.md` is read from there, and a language missing there falls back to the bundled
  `rules/<lang>.md`.

```bash
agent-kit rules          # show which file each language is read from
agent-kit rules --init   # copy the bundled rules there to start editing (never overwrites)
```

Both files have `{{LANG_NAME}}` / `{{GIT_LANG_NAME}}` placeholders, and they should say
the same thing in each language.

### Adding a rule with a local agent

```bash
agent-kit add-rule "never git push without asking" --dry-run   # show the diff only
agent-kit add-rule "never git push without asking"              # write it
agent-kit add-rule "..." --agent codex
```

The local `claude` (or `codex`) CLI gets the current rules and returns every language file
with the rule placed in the right section, translated, and merged with any rule it overlaps.
It runs with no tools in an empty directory. agent-kit checks the answer (every language present,
placeholders and first heading kept) before writing to your rules dir, and prints the diff.

## Changing a rule for every project

Edit your rules (or use `add-rule`), then:

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

## License

MIT, see [LICENSE](LICENSE).
