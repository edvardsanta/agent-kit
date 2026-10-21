---
name: agent-kit-procedures
description: "Use this skill when the user asks to save, document or update a reusable workflow for this repository (\"save this as a procedure\", \"document how we release\", \"remember these steps\"), or before carrying out a workflow that may already be documented in .agent-kit/procedures/. Trigger by intent, even when agent-kit is not named."
---

# agent-kit procedures

Project procedures are tracked Markdown workflows in `.agent-kit/procedures/`, shared by the users
and every agent working on this repository.

## Using a procedure

1. If `.agent-kit/procedures/INDEX.md` exists, read it before planning a workflow.
2. When an entry matches the task, read the whole procedure and follow it.

## Writing a procedure

Create or update a procedure only when the user explicitly asks to preserve a workflow.

1. Inspect the repository first: scripts, manifests, CI workflows, configuration and the existing
   procedures. Describe what this project actually does; never invent commands.
2. Write `.agent-kit/procedures/<kebab-case-name>.md` (subfolders are fine). Never overwrite a
   different existing procedure; update it only when that is what the user asked.
3. Format, in the repository's documentation language:
   - First line: `# <Title>`.
   - Then a blank line and a one-sentence summary of at most 160 characters; the index shows it.
   - Then the sections that apply: prerequisites, numbered steps, verification, rollback or
     recovery.
4. Run `agent-kit procedures init` from the repository root. It creates the folder's README if
   missing and regenerates `INDEX.md`; never edit `INDEX.md` by hand.
5. Show the user `git diff -- .agent-kit/procedures` (new files appear in `git status`). Do not
   commit unless they ask.

## Limits

- No secrets, tokens, credentials or content from outside the repository.
- No disposable scratch work: procedures are for workflows worth repeating.
- Do not include agent-kit or ai-memory comment markers.
