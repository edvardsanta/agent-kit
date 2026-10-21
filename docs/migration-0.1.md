# Migrating to the 0.1 CLI

`0.1.0.dev0` is the development version leading to the first tagged release. There are no earlier
tagged releases, so these notes cover commands and options that existed during development.

| Development command or option | 0.1 replacement |
| --- | --- |
| `agent-kit add-rule` | `agent-kit rules add` |
| `agent-kit rules add RULE` (global by default) | `agent-kit rules add RULE --scope global`; without it the rule goes to the project |
| `agent-kit rules --init` | `agent-kit rules init` |
| `agent-kit init --all` | `agent-kit sync` |
| `agent-kit init --lang LANG` | `--docs-lang LANG` (add `--chat-lang LANG` to pin chat) |
| `agent-kit init --hide-agent-files` | `agent-kit init --profile upstream` |
| positional repository arguments for `procedures` | `--repo PATH` |
| `--full-memory` or `--no-skills` | `--memory off`, `compact`, or `full` |

Languages are no longer defaulted to `pt`: `init` detects the documentation and Git languages
from the repository and fails when it cannot. The chat language is only written when
`--chat-lang` is given; a legacy `lang=` marker now fixes the documentation language only.

The `agent-init` command remains an alias for `agent-kit init` during the first pre-release. New
scripts should use `agent-kit init` directly.

For cross-platform installations, use `pipx install .` or `python -m pip install .`. `make install`
is only a convenience for Unix-like development checkouts.
