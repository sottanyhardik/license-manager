#!/usr/bin/env python3
"""PostToolUse(Edit|Write|MultiEdit) — fast, read-only syntax validation of the edited file.

Never modifies files (no auto-formatting: the repo has no formatter config, and silently
rewriting files could clobber user changes). Exit 2 = report the error back to Claude.
Checks: *.py (compile), *.json (parse; JSONC files such as tsconfig are skipped).
Anything else: no-op. Pure stdlib, < 50 ms.
"""
import json, os, sys

try:
    path = (json.load(sys.stdin).get("tool_input") or {}).get("file_path", "") or ""
except Exception:
    sys.exit(0)
if not path or not os.path.isfile(path) or "/node_modules/" in path:
    sys.exit(0)

err = None
try:
    if path.endswith(".py"):
        with open(path, "rb") as fh:
            compile(fh.read(), path, "exec", dont_inherit=True)
    elif path.endswith(".json"):
        base = os.path.basename(path)
        if not base.startswith(("tsconfig", "jsconfig")) and "/.vscode/" not in path:
            with open(path, encoding="utf-8") as fh:
                json.loads(fh.read())
except SyntaxError as e:
    err = f"{type(e).__name__}: {e.msg} (line {e.lineno})"
except ValueError as e:
    err = f"invalid JSON: {e}"
except Exception:
    sys.exit(0)

if err:
    print(f"post_edit_validate: {path}: {err} — fix before continuing.", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
