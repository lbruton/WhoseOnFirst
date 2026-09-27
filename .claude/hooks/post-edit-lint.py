#!/usr/bin/env python3
"""Post-edit lint hook for WhoseOnFirst (DEVS-90) — Python and JSON checks.

- .py: syntax check (in-process compile, no __pycache__), then flake8 from
  the repo venv
- .json: syntax validation

Claude Code drops plain stdout from PostToolUse hooks, so findings are
emitted as hookSpecificOutput.additionalContext JSON. Clean edits and files
outside the repo print nothing. Always exits 0 (non-blocking).

Also accepts Codex apply_patch payloads (patch text in tool_input.command)
so the same script can back a .codex/hooks.json if one is added.
"""

import json
import os
import re
import subprocess
import sys

# .claude/hooks/post-edit-lint.py -> repo root, so worktrees lint their own tree
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
TIMEOUT = 15
MAX_LINES = 10

PATCH_PATH_RE = re.compile(r"^\*\*\* (?:Add File|Update File|Move to): (.+)$")


def run_cmd(cmd):
    """Run a command from the repo root. Returns (returncode, output); never raises."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=PROJECT_DIR,
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode, "\n".join(output.splitlines()[:MAX_LINES])
    except (subprocess.TimeoutExpired, OSError):
        return 0, ""


def main_checkout():
    """Root of the main checkout when running in a worktree, else PROJECT_DIR."""
    rc, out = run_cmd(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"])
    if rc == 0 and out:
        return os.path.dirname(out.strip())
    return PROJECT_DIR


def find_flake8():
    """flake8 from the repo venv (worktrees fall back to the main checkout's venv)."""
    for root in dict.fromkeys([PROJECT_DIR, main_checkout()]):
        for venv in ("venv", ".venv"):
            candidate = os.path.join(root, venv, "bin", "flake8")
            if os.access(candidate, os.X_OK):
                return candidate
    return None


def edited_files(tool_name, tool_input, cwd):
    """Absolute paths of the files the tool call wrote."""
    if tool_name in ("Edit", "Write", "MultiEdit"):
        path = tool_input.get("file_path", "")
        return [path] if path else []
    if tool_name == "apply_patch":
        lines = str(tool_input.get("command", "")).splitlines()
        paths = []
        for i, line in enumerate(lines):
            m = PATCH_PATH_RE.match(line)
            if not m:
                continue
            # An Update followed by Move to only exists at the destination
            if line.startswith("*** Update File:") and i + 1 < len(lines) and lines[i + 1].startswith("*** Move to:"):
                continue
            paths.append(os.path.join(cwd, m.group(1).strip()))
        return paths
    return []


def in_repo(path):
    return os.path.realpath(path).startswith(PROJECT_DIR + os.sep)


def lint_file(file_path):
    """Return a list of findings for one file."""
    rel = os.path.relpath(os.path.realpath(file_path), PROJECT_DIR)
    findings = []

    if file_path.endswith(".py"):
        try:
            with open(file_path, encoding="utf-8") as f:
                compile(f.read(), rel, "exec")
        except SyntaxError as e:
            findings.append(f"syntax error ({rel}): line {e.lineno}: {e.msg}")
            return findings
        except (OSError, ValueError):
            return findings

        flake8 = find_flake8()
        if flake8:
            rc, output = run_cmd([flake8, rel, "--max-line-length=120"])
            if rc != 0 and output:
                findings.append(f"flake8 ({rel}):\n{output}")

    elif file_path.endswith(".json"):
        try:
            with open(file_path, encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            findings.append(f"json validation ({rel}): {e}")
        except (OSError, ValueError):
            pass

    return findings


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    if not isinstance(data, dict):
        sys.exit(0)

    tool_input = data.get("tool_input") or {}
    cwd = data.get("cwd") or os.getcwd()
    findings = []
    for path in dict.fromkeys(edited_files(data.get("tool_name", ""), tool_input, cwd)):
        if os.path.isfile(path) and in_repo(path):
            findings.extend(lint_file(path))

    if findings:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "[lint] " + "\n[lint] ".join(findings),
            }
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
