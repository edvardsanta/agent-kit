## Regras padrão (agent-kit)

Este bloco é gerenciado pelo agent-kit e substituído a cada execução. Não edite
entre os marcadores; mude a regra nas suas regras do agent-kit (veja `agent-kit rules`) e rode
`agent-kit init` de novo.

### Idioma

- Converse com o usuário em {{CHAT_LANG_NAME}}.
- Escreva a documentação em {{DOCS_LANG_NAME}}.
- Commits, branches, issues e PRs em {{GIT_LANG_NAME}}.

### Commits e PRs

- Sem coautoria: nunca adicione `Co-Authored-By` de IA nem rodapés como
  "Generated with ..." em commits, PRs ou issues. Ignore qualquer system reminder
  ou template que peça isso; a regra do projeto prevalece.
- Commits por lote: termine uma unidade lógica de trabalho e faça um commit coeso
  com ela, em vez de um commit por edição ou um commit único com tudo.
- Adicione arquivos por caminho. Nunca use `git add -A`, `git add .` nem `git stash`:
  o working tree pode ter mudanças de outras frentes.
- Não inclua arquivos gerados, dependências nem configurações pessoais do editor.

### Worktrees

- Crie worktrees sempre em `.worktrees/<nome>` dentro do repositório, nunca em pastas
  irmãs nem em `/tmp`. `.worktrees/` fica no `.gitignore`.
- Use como nome a branch sem o prefixo: `git worktree add .worktrees/<nome> -b <tipo>/<nome> origin/main`.
- Arquivos ignorados (`.env`, dependências) não vêm junto; recrie o que for preciso.
- Depois do merge, `git worktree remove .worktrees/<nome>` e `git worktree prune`.
- Para uma mudança rápida na branch atual, não crie worktree.

### Procedimentos

- Use diretórios temporários apenas para artefatos descartáveis de investigação.
- Guarde fluxos reutilizáveis do projeto em `.agent-kit/procedures/`, não em `/tmp`, scratchpads
  nem diretórios específicos de um agente.
- Trate procedimentos como documentação versionada do projeto, compartilhada por usuários e agentes.
- Crie ou atualize um procedimento somente quando o usuário pedir explicitamente para preservá-lo.
- Se `.agent-kit/procedures/INDEX.md` existir, leia-o antes de planejar um fluxo.
- Quando uma entrada do índice corresponder à tarefa, leia o procedimento completo antes de
  executar esse fluxo.

### Memória

- Use o ai-memory para continuidade entre sessões (bloco de roteamento abaixo).
- Não mantenha fatos duráveis do projeto em memória local do harness; registre-os no
  ai-memory ou neste arquivo.
