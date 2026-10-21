"""Smoke-test an installed agent-kit wheel from outside the source checkout."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(command, cwd, env):
    return subprocess.run(command, cwd=cwd, env=env, check=True,
                          capture_output=True, text=True)


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


if __name__ == "__main__":
    main()
