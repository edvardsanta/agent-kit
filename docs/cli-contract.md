# CLI contract

Status: accepted contract for the first public pre-release. Runtime behavior remains pre-release
until every item in the delivery sequence is complete.

## Product boundary

agent-kit prepares repositories for AI coding agents without depending on one agent harness. It:

1. initializes and synchronizes repository instructions;
2. manages personal and project rules;
3. manages reusable project procedures; and
4. diagnoses the local tools needed for those operations.

It is not an agent runtime, task runner, memory database, plugin system, or package manager.
Integrations may be invoked by agent-kit, but their internal features must not leak into unrelated
commands.

## Command grammar

The supported command tree is:

```text
agent-kit init [REPO]
agent-kit sync [ROOT]
agent-kit rules show
agent-kit rules init
agent-kit rules add [RULE]
agent-kit procedures init
agent-kit procedures add
agent-kit procedures list
agent-kit procedures show NAME
agent-kit procedures path
agent-kit doctor
```

Rules and procedures are plural command families. Actions below them are singular verbs. New
top-level commands require a new product responsibility; a convenient implementation detail is not
enough.

### Commands

`init` initializes a single repository or updates its complete agent-kit setup. It may run the
selected AI to generate project instructions. `REPO` defaults to the current directory.

`sync` reapplies deterministic managed state to already initialized repositories below `ROOT`. It
never invokes an AI. `ROOT` defaults to the current directory.

`rules` manages the personal baseline or a tracked project overlay. The default scope is global;
project scope requires `--scope project` and accepts `--repo PATH`.

`procedures` manages tracked workflows in one repository. Project selection always uses
`--repo PATH`, defaulting to the current repository. A second positional repository argument is not
supported.

`doctor` performs read-only diagnostics. It never repairs or installs anything.

## Interactive and non-interactive use

The same command supports people and scripts without guessing from incomplete input:

- A missing value may open an interactive prompt only when standard input is a terminal.
- Non-interactive commands fail with exit 2 and name the missing option; they never wait for input.
- `rules add` may prompt for the rule when `RULE` is omitted.
- `procedures add` is interactive by default. The user explains the workflow; the AI derives its
  title and agent-kit derives its filename.
- Scripts use `procedures add NAME --description TEXT`.
- Interactive prompts collect intent. They do not expose raw model prompts or implementation
  settings.

## Common behavior

### Repository selection

- `init [REPO]` and `sync [ROOT]` keep positional paths because the path is their primary operand.
- Resource families use `--repo PATH` consistently.
- Commands resolve the Git root from subdirectories.
- Paths written by a resource command cannot escape that resource's directory.

### Agent selection and trust

Generative commands accept:

```text
--agent auto|claude|codex
--trust
```

`init` additionally accepts `--agent none` for deterministic-only initialization. `auto` selects
Claude, then Codex. Unless `--trust` is explicit, agents receive read-only repository access and
project hooks, MCP servers, and agent-specific settings are ignored where the harness supports it.
The selected agent never writes repository files; agent-kit validates and applies its response.

### Preview and checking

- `--dry-run` performs validation and prints the proposed diff without writing.
- On a generative command, `--dry-run` still invokes the AI.
- `--check` is for deterministic convergence checks. It never invokes the AI and exits 1 when
  managed state is outdated.
- A command must finish all validation that can fail before its first repository write.
- Related writes are planned and applied as one change set.

### Output

- Requested data and diffs go to standard output.
- Progress, warnings, interactive prompts, and errors go to standard error.
- `list`, `show`, and `path` produce machine-consumable standard output without progress messages.
- Commands do not commit, push, install dependencies, or repair external tools.
- Output uses no color when it is redirected or when `NO_COLOR` is set.

### Exit status

| Status | Meaning |
| --- | --- |
| `0` | Success, including an already-current state. |
| `1` | `--check` found outdated managed state. |
| `2` | Invalid input, unsafe state, missing tool, rejected AI output, or operation failure. |
| `130` | Interrupted by the user. |

## Scope model

Global rules are personal configuration outside a checkout. Project rules and procedures are
tracked repository data under `.agent-kit/`.

| Resource | Global | Project |
| --- | --- | --- |
| Rules | Yes; default | Yes; additive overlay |
| Procedures | No | Yes |
| Generated `AGENTS.md` block | No | Yes |

Scope must be explicit in code and help text. A command cannot infer project scope merely because
it happens to run inside a Git repository.

## Generative contract

Every AI-powered operation follows the same pipeline:

```text
collect intent
  -> resolve repository and agent
  -> inspect repository read-only
  -> receive delimited structured output
  -> validate structure and paths
  -> show the change
  -> apply through Changes
```

An AI failure or rejected response leaves all files unchanged. Generated content is checked for
managed markers and suspicious commands or sensitive terms. The CLI tells the user what needs
review without claiming that model output is safe.

## First-release removals

There are no released tags, so the first public contract should not preserve accidental interfaces.
Remove these before the first release:

| Remove | Canonical replacement |
| --- | --- |
| `agent-kit add-rule` | `agent-kit rules add` |
| `agent-kit rules --init` | `agent-kit rules init` |
| `agent-kit init --all` | `agent-kit sync` |
| `agent-kit init --lang` | `--chat-lang` and `--docs-lang` |
| `agent-kit init --hide-agent-files` | `--profile upstream` |
| positional repositories under `procedures` | `--repo PATH` |

Keep `agent-init` only through the first pre-release as a documented shortcut for `agent-kit init`.
Its removal or stabilization must be decided before declaring the CLI stable.

## Memory integration

Memory integration uses one bounded option:

```text
--memory off|compact|full
```

The implementation translates that value into ai-memory arguments. Other commands do not know
about ai-memory installation details. The default is `compact`; the `upstream` profile defaults to
`off` unless the user selects a mode explicitly.

`--tracked` should also be absorbed by the `own` profile once profile behavior is covered by tests.
`upstream` remains the safe profile for third-party clones. Until profile persistence is designed,
profiles are explicit command options rather than hidden global state.

## Delivery sequence

1. [x] Align parser definitions and help output with this command tree; remove compatibility paths.
2. [x] Centralize shared agent, memory, preview, output, and exit-status behavior.
3. [x] Complete procedure discovery with a generated index referenced by the managed rules.
4. [x] Add `pyproject.toml`, packaged rules/prompts, and cross-platform console scripts.
5. [x] Add unit and installed-wheel CI coverage across Linux, macOS, and Windows.
6. [ ] Finish dogfooding initialization, synchronization, rules, and procedures in representative
   repositories. agent-kit itself now uses its generated procedure registry.
7. [x] Reconcile the current version constant with the first tagged release and publish migration
   notes.

Features outside this sequence remain deferred until the first-release contract is implemented and
tested.
