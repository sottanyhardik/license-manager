#!/usr/bin/env python3
"""Stop hook — user-visible verification reminder after application code changes.

When the working tree contains changes under backend/, frontend/, master-data-service/
or mds-client/, shows ONE reminder per distinct diff state (deduplicated per session via a
hash file in $TMPDIR), so it does not nag on every turn. Never blocks (always exit 0) and
never forces Claude to continue. Read-only apart from that tiny dedupe file.
"""
import hashlib, json, os, subprocess, sys, tempfile

try:
    data = json.load(sys.stdin)
except Exception:
    data = {}
if data.get("stop_hook_active"):
    sys.exit(0)
root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
paths = ["backend", "frontend", "master-data-service", "mds-client"]
try:
    st = subprocess.run(["git", "status", "--porcelain", "--", *paths], cwd=root,
                        capture_output=True, text=True, timeout=8).stdout
    if not st.strip():
        sys.exit(0)
    diff = subprocess.run(["git", "diff", "HEAD", "--", *paths], cwd=root,
                          capture_output=True, text=True, timeout=8).stdout
except Exception:
    sys.exit(0)

digest = hashlib.sha1((st + diff).encode()).hexdigest()
sid = "".join(ch for ch in str(data.get("session_id", "default")) if ch.isalnum() or ch == "-")[:64]
marker = os.path.join(tempfile.gettempdir(), f"lm-claude-stop-{sid}")
try:
    with open(marker) as fh:
        if fh.read() == digest:
            sys.exit(0)
except OSError:
    pass
try:
    with open(marker, "w") as fh:
        fh.write(digest)
except OSError:
    pass

n = len(st.strip().splitlines())
print(json.dumps({"systemMessage":
    f"Verify: {n} application path(s) changed. Before calling it done: /quality-gate, "
    "/review-diff (independent review), the domain auditor if CIF/BOE/allotment/invoice code "
    "changed, then /report."}))
sys.exit(0)
