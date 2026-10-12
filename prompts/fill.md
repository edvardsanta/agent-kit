You are setting up agent instructions for the repository in the current directory.

Goal: write the project-specific part of `AGENTS.md`. The file already contains blocks
delimited by `<!-- agent-kit:start -->` / `<!-- agent-kit:end -->` and
`<!-- ai-memory:start -->` / `<!-- ai-memory:end -->`. Never edit, move or duplicate
those blocks. Write your content outside them: after the agent-kit block and before the ai-memory block (create a `# ` title at the top if missing).

Inspect the repo first (README, manifests such as package.json / pyproject.toml / Makefile /
CMakeLists.txt / *.csproj, CI workflows, lint and format configs, top-level directories,
`git log --oneline -30`). Then write these sections, in {{LANG_NAME}}:

1. Overview: what the project is, in 2-4 lines.
2. Repository layout: only the directories that matter, one line each.
3. Environment and commands: build, test, lint, format, run. Only commands you verified
   exist in manifests, Makefile or CI. Mark the fast one for a single test if there is one.
4. Conventions: style, architecture rules and naming you can actually observe in the code
   or in config files. No generic advice.
5. Pitfalls: generated directories not to touch, large trees to search by symbol instead of
   reading, slow builds, required services.

Rules:
- Do not invent. If you cannot verify something, leave it out.
- Do not repeat what the agent-kit block already says (language, commits, worktrees, memory).
- Keep it under 120 lines. Short bullets beat prose.
- If `AGENTS.md` already has project content outside the managed blocks, keep what is
  still correct and fix what is wrong; do not rewrite it from scratch.
- Deduplicate (mandatory, do it before finishing): delete every existing section or
  subsection outside the managed blocks whose topic is covered by the agent-kit block:
  language, commit authorship/co-authorship, staging rules, worktrees, ai-memory. A
  "Worktrees" heading left in the file is a failure. Keep only what is project-specific
  (commit prefix format, branch naming, PR template, how to install deps in a worktree),
  folded into a short "Git conventions" section. After editing, re-read the file and
  check that no heading repeats a topic of the agent-kit block.
- Do not touch `CLAUDE.md`. Do not run git commit or git add. Do not install anything.
