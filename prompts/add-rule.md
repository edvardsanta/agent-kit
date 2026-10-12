You maintain the default rules that agent-kit injects into every project's `AGENTS.md`.
Below are the current rules files, one per language. Add this new rule to every file:

<rule>
{{RULE}}
</rule>

How to edit:
- Put the rule in the section where it belongs; create a new `### ` section only if none fits.
- Write it in each file's own language, matching the existing tone: short imperative bullets,
  same wrapping width, no new formatting styles.
- If an existing rule already covers it, merge them instead of adding a duplicate. If an
  existing rule contradicts it, the new rule wins: rewrite or remove the old one.
- Keep the meaning identical across languages.
- Change nothing else. Keep `{{LANG_NAME}}` and `{{GIT_LANG_NAME}}` exactly as they are, and
  keep the first heading and the introductory paragraph unchanged.

Output format (mandatory): print only the full new content of every file, each preceded by
its header line exactly as below, and end with `=== end ===`. No code fences, no comments
before or after.

