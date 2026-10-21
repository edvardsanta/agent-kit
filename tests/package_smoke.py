"""Smoke-test an installed agent-kit wheel from outside the source checkout."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(command, cwd, env):
    # a pipe, not a console: the child encodes stdout with the locale code page (cp1252 on Windows)
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"{command} exited with {result.returncode}:\n{result.stderr}")
    return result


def main():
    agent_kit = shutil.which("agent-kit")
    agent_init = shutil.which("agent-init")
    if not agent_kit or not agent_init:
        raise RuntimeError("installed console commands were not found on PATH")

    with tempfile.TemporaryDirectory(prefix="agent-kit-package-smoke-") as temporary:
        root = Path(temporary)
        env = {**os.environ, "AGENT_KIT_RULES": str(root / "user-rules")}
        version = run([agent_kit, "--version"], root, env)
        if "agent-kit " not in version.stdout:
            raise RuntimeError("agent-kit --version returned unexpected output")

        rules = run([agent_kit, "rules", "show"], root, env)
        if "(bundled)" not in rules.stdout:
            raise RuntimeError("installed package could not load its bundled rules")

        repo = root / "repo"
        repo.mkdir()
        run(["git", "init", "-q"], repo, env)
        # non-ASCII text catches reads that fall back to the locale encoding (cp1252 on Windows)
        (repo / "README.md").write_text(
            "This is a smoke test for the installed package and it checks that it “works”.\n",
            encoding="utf-8")
        run([agent_init, str(repo), "--agent", "none", "--memory", "off"], root, env)
        agents = repo / "AGENTS.md"
        if not agents.is_file() or "agent-kit:start" not in agents.read_text(encoding="utf-8"):
            raise RuntimeError("agent-init did not initialize the smoke-test repository")
        if not (repo / ".claude" / "skills" / "agent-kit-rules" / "SKILL.md").is_file():
            raise RuntimeError("agent-init did not install the packaged agent skills")

        # the diff goes to stdout; "→" has no cp1252 mapping
        overlay = repo / ".agent-kit" / "rules" / "en.md"
        overlay.parent.mkdir(parents=True)
        overlay.write_text("### Project\n\n- Pipelines run lint → test → build.\n", encoding="utf-8")
        diff = run([agent_init, str(repo), "--agent", "none", "--memory", "off", "--dry-run"], root, env)
        if "lint → test → build" not in diff.stdout:
            raise RuntimeError("agent-init --dry-run did not print the project rule in its diff")


if __name__ == "__main__":
    main()
