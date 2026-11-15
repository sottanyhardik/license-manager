#!/usr/bin/env python3
"""PreToolUse(Bash) guard — blocks commands that cross the autonomy boundary.

Policy: .claude/rules/safety.md. Exit 2 = block (stderr is shown to Claude).
Exit 0 = defer to normal permission rules. Pure stdlib, no Node needed.
"""
import json, re, sys

try:
    cmd = (json.load(sys.stdin).get("tool_input") or {}).get("command", "") or ""
except Exception:
    sys.exit(0)

c = " ".join(cmd.split())
BLOCK = [
    (r"\bgit\s+push\b.*(--force\b|--force-with-lease\b|\s-f\b|\s\+\S)", "force push"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard (destructive)"),
    (r"\bgit\s+clean\s+-[a-z]*f", "git clean -f (destructive)"),
    (r"\bgit\s+branch\s+-D\b", "force branch delete"),
    (r"\bgit\s+(checkout|restore)\s+(--\s+)?\.(\s|$)", "discarding all working-tree changes"),
    (r"\bgit\s+filter-(branch|repo)\b", "history rewrite"),
    (r"\brm\s+-[a-z]*r[a-z]*f?\s+(/|~|\$HOME|\.\.?/?)(\s|$)", "recursive delete of root/home/repo"),
    (r"--dangerously-skip-permissions|bypassPermissions", "permission bypass"),
    (r"\b(ssh|scp|rsync|sftp)\b\s", "remote server access (deploys need approval)"),
    (r"\b(systemctl|service)\s+(start|stop|restart|reload|enable|disable)\b", "service control"),
    (r"(backend/deploy/|scripts/deploy|deploy\.sh|fab\s+deploy)", "deployment script"),
    (r"\b(DROP\s+(DATABASE|TABLE|SCHEMA)|TRUNCATE\s+)", "irreversible SQL"),
    (r"\bmanage\.py\s+(flush|reset_db|sqlflush)\b", "database wipe"),
    (r"\b(cat|less|more|head|tail|bat|cp|base64|xxd)\b[^|;&]*(\.env(\s|$|\.local|\.production)|\.env_dgft|id_rsa|\.pem\b)", "secret file disclosure"),
    (r"\b(printenv|env)\s*($|\|)", "environment dump (may contain secrets)"),
    (r"(curl|wget)[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b", "piping remote script to shell"),
]
for pat, why in BLOCK:
    if re.search(pat, c, re.IGNORECASE):
        print(f"BLOCKED by .claude/hooks/guard_bash.py: {why}. "
              "This crosses the autonomy boundary in .claude/rules/safety.md — "
              "ask the human to run it or to approve it explicitly.", file=sys.stderr)
        sys.exit(2)

# Non-local DB targets for migrate/manage commands
LOCAL = ("localhost", "127.0.0.1", "::1", "db", "postgres", "")
for m in re.finditer(r"\b(?:MDS_)?DB_HOST=([^\s;&|]+)", c):
    host = m.group(1).strip("'\"")
    if "$" in host or host in LOCAL:  # shell expansions are checked at runtime by the scripts
        continue
    print("BLOCKED: DB_HOST points to a non-local database. Production/remote DBs need human approval.", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
