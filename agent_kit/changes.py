"""Transactional file changes shared by mutating commands."""

import difflib
import os
import sys

from . import log


class Changes:
    """Collect file writes so one plan can be applied, diffed, or checked."""

    def __init__(self, repo):
        self.repo = repo
        self.pending = {}

    def read(self, path):
        if path in self.pending:
            return self.pending[path][0]
        return path.read_text() if path.exists() else None

    def write(self, path, text, message):
        if self.read(path) != text:
            messages = self.pending.get(path, (None, []))[1]
            self.pending[path] = (text, messages + [message])

    def rel(self, path):
        return os.path.relpath(path, self.repo)

    def apply(self):
        for path, (text, messages) in self.pending.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            for message in messages:
                log(message)

    def diff(self):
        for path, (text, _) in self.pending.items():
            old = path.read_text() if path.exists() else ""
            relative = self.rel(path)
            sys.stdout.writelines(difflib.unified_diff(
                old.splitlines(True), text.splitlines(True),
                f"a/{relative}", f"b/{relative}"))
