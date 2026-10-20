# Migrating to the 0.1 CLI

`0.1.0.dev0` is the development version leading to the first tagged release. There are no earlier
tagged releases, so these notes cover commands and options that existed during development.

| Development command or option | 0.1 replacement |
| --- | --- |
| `agent-kit add-rule` | `agent-kit rules add` |
| `agent-kit rules --init` | `agent-kit rules init` |
| `agent-kit init --all` | `agent-kit sync` |
| `agent-kit init --lang LANG` | `--chat-lang LANG --docs-lang LANG` |
| `agent-kit init --hide-agent-files` | `agent-kit init --profile upstream` |
| positional repository arguments for `procedures` | `--repo PATH` |
| `--full-memory` or `--no-skills` | `--memory off`, `compact`, or `full` |

The `agent-init` command remains an alias for `agent-kit init` during the first pre-release. New
scripts should use `agent-kit init` directly.

For cross-platform installations, use `pipx install .` or `python -m pip install .`. `make install`
is only a convenience for Unix-like development checkouts.
