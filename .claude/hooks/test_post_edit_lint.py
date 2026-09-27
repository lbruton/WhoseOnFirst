#!/usr/bin/env python3
"""Contract tests for post-edit-lint.py (DEVS-90).

Run: python3 -m unittest discover -s .claude/hooks -p 'test_*.py'

Claude Code drops plain stdout from PostToolUse hooks, so findings must come
back as hookSpecificOutput.additionalContext JSON, and clean edits must print
nothing. Scratch files go in a temp dir inside the repo, because the hook
skips files outside the repo root.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
HOOK = os.path.join(HERE, "post-edit-lint.py")
ROOT = os.path.dirname(os.path.dirname(HERE))

_spec = importlib.util.spec_from_file_location("post_edit_lint", HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)
HAS_FLAKE8 = hook.find_flake8() is not None


def run_hook(payload, raw=None):
    res = subprocess.run(
        ["python3", HOOK],
        input=raw if raw is not None else json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    )
    assert res.returncode == 0, f"hook exited {res.returncode}: {res.stderr}"
    return res.stdout.strip()


def context_of(stdout):
    assert stdout, "expected JSON output, got nothing"
    out = json.loads(stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PostToolUse"
    return out["additionalContext"]


class PostEditLintTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="hooktest-scratch-", dir=ROOT)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def scratch(self, name, body):
        path = os.path.join(self.dir, name)
        with open(path, "w") as f:
            f.write(body)
        return path

    def edit(self, path, tool="Edit"):
        return run_hook({"tool_name": tool, "tool_input": {"file_path": path}})

    def test_python_syntax_error_is_reported(self):
        ctx = context_of(self.edit(self.scratch("broken.py", "def f(:\n    pass\n")))
        self.assertIn("syntax error", ctx)

    def test_clean_python_is_silent(self):
        self.assertEqual(self.edit(self.scratch("clean.py", '"""Clean."""\n\nVALUE = 1\n'), "Write"), "")

    def test_syntax_check_leaves_no_pycache(self):
        self.edit(self.scratch("clean.py", '"""Clean."""\n\nVALUE = 1\n'))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "__pycache__")))

    @unittest.skipUnless(HAS_FLAKE8, "no venv with flake8 found")
    def test_flake8_violation_is_reported(self):
        ctx = context_of(self.edit(self.scratch("style.py", "import os\n")))
        self.assertIn("F401", ctx)

    def test_invalid_json_is_reported(self):
        ctx = context_of(self.edit(self.scratch("broken.json", "{ not json")))
        self.assertIn("json", ctx.lower())

    def test_file_outside_repo_is_skipped(self):
        outside = tempfile.mkdtemp(prefix="hooktest-outside-")
        try:
            path = os.path.join(outside, "broken.json")
            with open(path, "w") as f:
                f.write("{ not json")
            self.assertEqual(self.edit(path), "")
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_unrelated_tool_and_malformed_payload_are_silent(self):
        self.assertEqual(run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}}), "")
        self.assertEqual(run_hook(None, raw="not json"), "")


if __name__ == "__main__":
    unittest.main()
