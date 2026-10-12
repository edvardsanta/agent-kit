# agent-kit

CLI pessoal para padronizar `AGENTS.md` / `CLAUDE.md` entre projetos.

```bash
agent-init ~/repos/meu-projeto --lang pt            # docs/conversa em pt, commits em pt
agent-init . --lang pt --git-lang en                # docs em pt, commits/issues/PRs em inglês
agent-init . --agent codex                          # codex preenche as seções do projeto
agent-init . --agent none                           # só a parte determinística
agent-init . --migrate-claude                       # CLAUDE.md antigo -> AGENTS.md + stub
agent-init ~/repos/rpcs3 --hide-agent-files         # fork/upstream: nada entra no diff
```

## O que faz

1. Insere/atualiza o bloco `<!-- agent-kit:start -->` no `AGENTS.md` (regras em `rules/pt.md`, `rules/en.md`):
   idioma, sem coautoria, commits por lote, worktrees em `.worktrees/`, uso do ai-memory.
2. `CLAUDE.md` vira só `@AGENTS.md`.
3. `.worktrees/` vai para `.git/info/exclude` (use `--tracked` para o `.gitignore` versionado).
4. `.claude/settings.local.json` com `attribution` vazio (desliga o Co-Authored-By do Claude Code).
5. `ai-memory install-instructions` (bloco de roteamento + skills; `--no-skills`, `--full-memory`).
6. Um agente (`claude -p` ou `codex exec`) lê o repo e escreve visão geral, comandos, convenções e armadilhas
   fora dos blocos gerenciados (`prompts/fill.md`).

Idempotente: o idioma fica gravado no marcador, então rodar de novo não troca o idioma.
Nunca faz commit.

## Mudar uma regra para todos os projetos

Edite `rules/*.md` e rode `agent-init` de novo em cada repo (`--agent none` é rápido).
