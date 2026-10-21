---
name: agent-kit-rules
description: "Use this skill when the user wants to add, change or remove a rule for agents in this repository: \"always X\", \"never Y\", \"from now on...\", \"add a rule\", \"agents must...\". Also when they ask to make a rule apply to all of their repositories. Trigger by intent, even when agent-kit is not named."
---

# agent-kit rules

This repository's `AGENTS.md` starts with a block managed by agent-kit, between
`agent-kit:start` and `agent-kit:end` comment markers. Never edit inside that block and never write
those markers yourself: agent-kit regenerates the block from rule files.

## Project rule (default)

A rule the user asks for belongs to this project unless they say it should apply to all of their
repositories.

1. Edit every file in `.agent-kit/rules/`: `en.md` and `pt.md`. If one is missing, create it
   starting with its heading line, `## Project rules` in `en.md` and `## Regras do projeto` in
   `pt.md`.
2. Write the rule in each file's own language with the same meaning: a short imperative bullet
   matching the existing ones. Put it under the heading, or under a `### ` subsection that fits.
3. If an existing rule overlaps, merge them; if one contradicts it, the new rule wins: rewrite or
   remove the old one. Change nothing else.
4. Run `agent-kit init --agent none --memory off` from the repository root. It renders the rules
   into the managed block and fails if a file contains a managed-block marker.
5. Show the user `git diff -- .agent-kit/rules AGENTS.md`. Do not commit unless they ask.

## Rule for all repositories

Only when the user says the rule is personal or should apply everywhere:

1. Run `agent-kit rules init` (it never overwrites), then `agent-kit rules show` to find the
   personal rules directory and its `en.md` and `pt.md`.
2. Edit both files as above. Keep every `{{...}}` placeholder and the first heading unchanged.
3. Tell the user to apply it with `agent-kit sync <folder with their repositories>`; run it only if
   they ask.

## Limits

- Rules are instructions for agents, not documentation: keep them short, concrete and checkable.
- Never put secrets, tokens or credentials in a rule.
