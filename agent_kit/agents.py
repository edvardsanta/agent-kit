"""Safe adapters for supported local AI CLIs."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from . import InitError, log


def resolve_exe(name):
    executable = shutil.which(name)
    if not executable:
        raise InitError(f"{name} not found in PATH")
    if "/.asdf/shims/" in executable:
        result = subprocess.run(["asdf", "which", name], cwd=Path.home(),
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        executable = result.stdout.strip() or executable
    return executable


def select_agent(requested, allow_none=False):
    """Resolve auto-selection before any repository writes happen."""
    if requested == "none":
        if allow_none:
            return "none"
        raise InitError("this command requires an agent; choose Claude or Codex")
    if requested in ("claude", "codex"):
        if not shutil.which(requested):
            suffix = ", or use --agent none" if allow_none else ""
            raise InitError(
                f"{requested} was not found; no files were changed. Install it, choose another agent{suffix}")
        resolve_exe(requested)
        return requested
    for candidate in ("claude", "codex"):
        if shutil.which(candidate):
            return candidate
    suffix = ", or use --agent none" if allow_none else ""
    raise InitError(
        f"no supported agent found; no files were changed. Install Claude or Codex{suffix}")


def agent_candidates(requested, allow_none=False):
    """Agents to try in order: the one requested, or with `auto` every installed one."""
    if requested != "auto":
        return [select_agent(requested, allow_none)]
    found = [candidate for candidate in ("claude", "codex") if shutil.which(candidate)]
    return found or [select_agent(requested, allow_none)]


def with_fallback(agents, attempt):
    """Return `attempt(agent)` for the first agent that succeeds, moving on after each failure.

    `attempt` must not change anything before it can fail: a failed agent leaves no trace.
    """
    failures = []
    for index, agent in enumerate(agents):
        try:
            return attempt(agent)
        except InitError as error:
            if index == len(agents) - 1:
                if not failures:
                    raise
                raise InitError("every agent failed: " + "; ".join(failures + [f"{agent}: {error}"]))
            failures.append(f"{agent}: {error}")
            log(f"{agent} failed: {error}; trying {agents[index + 1]}")


# The prompt goes through stdin, never argv: on Windows `claude`/`codex` are often npm `.cmd`
# shims, and cmd.exe cuts a command-line argument at its first newline.


def ask_agent(agent, prompt):
    """Run an agent without tools or repository access."""
    with tempfile.TemporaryDirectory(prefix="agent-kit-") as temporary:
        output = Path(temporary) / "answer.md"
        if agent == "claude":
            command = [resolve_exe("claude"), "-p", "--output-format", "text", "--tools", ""]
        else:
            command = [resolve_exe("codex"), "exec", "--skip-git-repo-check", "--sandbox", "read-only",
                       "-o", str(output), "-"]
        result = subprocess.run(command, cwd=temporary, input=prompt,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise InitError(f"{agent} exited with {result.returncode}: {result.stderr.strip()[-500:]}")
        return output.read_text(encoding="utf-8") if agent == "codex" else result.stdout


def ask_repo_agent(repo, agent, prompt, trust, activity):
    """Let an agent inspect a repository read-only and return its answer."""
    with tempfile.TemporaryDirectory(prefix="agent-kit-") as temporary:
        output = Path(temporary) / "answer.md"
        if agent == "claude":
            command = [resolve_exe("claude"), "-p", "--output-format", "text",
                       "--tools", "Read", "Glob", "Grep", "Bash",
                       "--allowedTools", "Read", "Glob", "Grep",
                       "Bash(git log:*)", "Bash(git ls-files:*)", "Bash(ls:*)"]
            if not trust:
                command += ["--setting-sources", "user", "--strict-mcp-config"]
        else:
            command = [resolve_exe("codex"), "exec", "--sandbox", "read-only",
                       "-o", str(output), "-"]
        mode = "trusted" if trust else "read-only, project config ignored"
        log(f"{agent}: {activity} ({mode}; this can take a minute)...")
        result = subprocess.run(command, cwd=repo, input=prompt,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise InitError(f"{agent} exited with {result.returncode}: {result.stderr.strip()[-500:]}")
        return output.read_text(encoding="utf-8") if agent == "codex" else result.stdout
