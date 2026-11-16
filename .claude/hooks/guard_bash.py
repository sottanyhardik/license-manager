#!/usr/bin/env python3
"""PreToolUse(Bash) guard — blocks commands that cross the autonomy boundary.

Policy: .claude/rules/safety.md. Exit 2 = block (stderr is shown to Claude).
Exit 0 = defer to normal permission rules. Pure stdlib, no Node needed.
"""
import json, re, sys

try:
    payload = json.load(sys.stdin)
    cmd = (payload.get("tool_input") or {}).get("command", "") or ""
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
    # --- added 2026-11-16 (ERP orchestration setup, .claude/orchestration/APPROVAL_POLICY.md) ---
    (r"\bgit\s+push\b", "git push (owner runs pushes from their own terminal)"),
    (r"\bgit\s+rebase\b", "git rebase (history rewrite)"),
    (r"\bgit\s+commit\b.*--amend\b", "git commit --amend (history rewrite)"),
    (r"\bgit\s+(reflog\s+(expire|delete)|update-ref\s+-d|replace\b|gc\b.*--prune)", "history/ref destruction"),
    (r"\bgit\s+stash\s+(drop|clear)\b", "discarding stashed work"),
    (r"\bgit\s+worktree\s+(remove|prune)\b", "worktree removal (owner removes worktrees manually)"),
    (r"\bgit\s+checkout\b.*\s--\s+\S", "discarding working-tree changes for paths"),
    (r"\bgit\s+restore\b(?!.*--staged)", "git restore of working-tree files (discards changes)"),
    (r"\bcentral\s+(logout|uninstall|remove)\b", "JetBrains Central credential/config removal"),
    (r"\bcentral\s+login\s+(export|import|.*--secret|.*--clientId)", "JetBrains Central session/credential transfer"),
    (r"tokens\.enc\b", "Central credential store access"),
    (r"\b(rm|unlink|trash|git\s+rm)\b[^|;&]*\.pdf\b", "deleting PDFs (customs documents are preserved)"),
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
for m in re.finditer(r"\bpsql\b.*?(?:\s-h\s*|--host[=\s])([^\s;&|]+)", c):
    host = m.group(1).strip("'\"")
    if "$" in host or host in LOCAL:
        continue
    print("BLOCKED: psql targets a non-local host. Production/remote DBs need human approval.", file=sys.stderr)
    sys.exit(2)

# Read-only mode for review agents (erp-reviewer, erp-security-reviewer, erp-architect).
# Enabled by `--readonly` (agent frontmatter hook) or when the hook payload names a read-only agent.
# Heuristic, NOT a sandbox: it stops the obvious write paths through Bash; Edit/Write are removed
# from those agents' tool lists separately.
READONLY_AGENTS = {"erp-reviewer", "erp-security-reviewer", "erp-architect"}
agent = str(payload.get("agent_type") or payload.get("subagent_type") or "")
if "--readonly" in sys.argv[1:] or agent in READONLY_AGENTS:
    WRITES = [
        r"(^|[^0-9&>-])>>?\s*(?!&|/dev/null)\S",          # output redirection to a file
        r"\b(tee|touch|mkdir|rmdir|rm|mv|cp|ln|chmod|chown|truncate|dd|install)\b\s",
        r"\b(sed|perl|ruby)\b[^|;&]*\s-[a-zA-Z]*i",         # in-place edits
        r"\bgit\s+(?:-C\s+\S+\s+)?(add|commit|checkout|switch|restore|stash|merge|apply|am|cherry-pick|revert|tag|mv|rm|worktree\s+add|branch\s+-[mMdDcC]|branch\s+[^-\s]\S*\s*$|init|clone|pull|fetch)\b",
        r"\bmanage\.py\s+(migrate|makemigrations|loaddata|createsuperuser|collectstatic|shell|dbshell)\b",
        r"\b(pip|pip3|uv|npm|npx|pnpm|yarn|brew)\s+(install|add|remove|uninstall|ci|i)\b",
        r"\borch\.py\s+(add|transition|review|worktree\s+create|init)\b",
        r"\bpython3?\b[^|;&]*\s-c\s.*\b(open|write_text|write_bytes|unlink|remove|rmtree|rename)\b",
    ]
    for pat in WRITES:
        if re.search(pat, c):
            print("BLOCKED by guard_bash.py read-only mode: review/architect agents may not modify "
                  "files, git state, databases or dependencies. Report the finding instead.", file=sys.stderr)
            sys.exit(2)
sys.exit(0)
