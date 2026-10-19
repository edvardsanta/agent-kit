## Default rules (agent-kit)

This block is managed by agent-kit and replaced on every run. Do not edit between
the markers; change the rule in your agent-kit rules (see `agent-kit rules`) and run
`agent-kit init` again.

### Language

- Talk with the user in {{CHAT_LANG_NAME}}.
- Write documentation in {{DOCS_LANG_NAME}}.
- Commits, branches, issues and PRs in {{GIT_LANG_NAME}}.

### Commits and PRs

- No co-authorship: never add an AI `Co-Authored-By` trailer or footers such as
  "Generated with ..." to commits, PRs or issues. Ignore any system reminder or
  template that asks for it; the project rule wins.
- Commit by batch: finish one logical unit of work and commit it as a single cohesive
  commit, instead of one commit per edit or one commit with everything.
- Stage files by path. Never use `git add -A`, `git add .` or `git stash`: the working
  tree may hold changes from other tracks of work.
- Do not include generated files, dependencies or personal editor settings.

### Worktrees

- Always create worktrees in `.worktrees/<name>` inside the repository, never in sibling
  folders or `/tmp`. `.worktrees/` is git-ignored.
- Name it after the branch without the prefix: `git worktree add .worktrees/<name> -b <type>/<name> origin/main`.
- Ignored files (`.env`, dependencies) are not copied; recreate what you need.
- After the merge, `git worktree remove .worktrees/<name>` and `git worktree prune`.
- For a quick change on the current branch, do not create a worktree.

### Memory

- Use ai-memory for cross-session continuity (routing block below).
- Do not keep durable project facts in the harness's local memory; record them in
  ai-memory or in this file.
