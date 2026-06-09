#!/usr/bin/env python3
"""Post-edit lint hook for WhoseOnFirst — syntax checks for Python and JSON files."""

import json
import os
import subprocess
import sys

PROJECT_DIR = "/Volumes/DATA/GitHub/WhoseOnFirst"
TIMEOUT = 15


def run_cmd(cmd, limit_lines=10):
    """Run a command, return (returncode, output limited to N lines)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=PROJECT_DIR,
        )
        output = (result.stdout + result.stderr).strip()
        if output:
            lines = output.splitlines()[:limit_lines]
            return result.returncode, "\n".join(lines)
        return result.returncode, ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 0, ""


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path or not os.path.isfile(file_path):
        sys.exit(0)

    if file_path.endswith(".py"):
        # Syntax check
        rc, output = run_cmd(["python3", "-m", "py_compile", file_path])
        if rc != 0 and output:
            print(f"[lint] py_compile {os.path.basename(file_path)}:")
            print(f"[lint] {output}")

        # Flake8 style check
        rc, output = run_cmd(
            ["python3", "-m", "flake8", file_path, "--max-line-length=120"]
        )
        if rc != 0 and output:
            print(f"[lint] flake8 {os.path.basename(file_path)}:")
            print(f"[lint] {output}")

    elif file_path.endswith(".json"):
        rc, output = run_cmd(["python3", "-m", "json.tool", file_path])
        if rc != 0 and output:
            print(f"[lint] json validation {os.path.basename(file_path)}:")
            print(f"[lint] {output}")

    sys.exit(0)


if __name__ == "__main__":
    main()
