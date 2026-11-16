#!/usr/bin/env python3
"""PreToolUse(Bash) — fast checks that run only when Claude invokes `git commit`.

Blocks (exit 2) when the commit would include:
  * secret files (.env, .env.local/.production, .env_dgft, *.pem, *.key, id_rsa*)
  * high-confidence secret material in added lines (private keys, provider tokens)
  * Python files with syntax errors
Otherwise allows the commit and, if application source is included, shows the user a
reminder that the CI-equivalent gates and an independent review must have run.
The full gate suite is NOT run here: it needs Postgres and takes minutes — hooks must be fast.
Read-only: never stages, unstages, or edits anything.
"""
import json, re, subprocess, sys

try:
    cmd = (json.load(sys.stdin).get("tool_input") or {}).get("command", "") or ""
except Exception:
    sys.exit(0)
c = " ".join(cmd.split())
if not re.search(r"\bgit\s+(-C\s+\S+\s+)?commit\b", c):
    sys.exit(0)

m = re.search(r"\bgit\s+-C\s+(\S+)", c)
cwd = m.group(1).strip("'\"") if m else None


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=8).stdout
    except Exception:
        return ""


files = set(git("diff", "--cached", "--name-only", "--diff-filter=ACMR").split())
diff_args = ["diff", "--cached", "-U0", "--diff-filter=ACMR"]
if re.search(r"\scommit\b.*(\s-[a-zA-Z]*a[a-zA-Z]*\b|\s--all\b)", c):  # commit -a / -am / --all
    files |= set(git("diff", "--name-only", "--diff-filter=ACMR").split())
    diff_args = ["diff", "HEAD", "-U0", "--diff-filter=ACMR"]

SECRET_FILE = re.compile(
    r"(^|/)(\.env(\.local|\.production|\.prod)?|\.env_dgft|id_rsa[^/]*|[^/]+\.(pem|key|p12|pfx))$"
)
problems = [f"secret-like file staged: {f}" for f in sorted(files) if SECRET_FILE.search(f)]

SECRET_TEXT = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b|\bsk-ant-[A-Za-z0-9_-]{20,}|"
    r"\bsk-[A-Za-z0-9]{32,}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bxox[abpr]-[A-Za-z0-9-]{10,}"
)
for line in git(*diff_args).splitlines():
    if line.startswith("+") and not line.startswith("+++"):
        hit = SECRET_TEXT.search(line)
        if hit:  # never echo the full value
            problems.append(f"possible secret/token in added lines ({hit.group(0)[:6]}…)")
            break

for f in sorted(x for x in files if x.endswith(".py")):
    src = git("show", f":{f}")
    if not src:
        continue
    try:
        compile(src, f, "exec", dont_inherit=True)
    except SyntaxError as e:
        problems.append(f"syntax error in {f} line {e.lineno}: {e.msg}")

if problems:
    print("BLOCKED by .claude/hooks/pre_commit_check.py:\n  - " + "\n  - ".join(problems)
          + "\nUnstage/fix these (never commit secrets — .claude/rules/safety.md).", file=sys.stderr)
    sys.exit(2)

APP = re.compile(r"^(backend|frontend|master-data-service|mds-client)/")
app_files = [f for f in files if APP.match(f)]
if app_files:
    print(json.dumps({"systemMessage":
        f"pre-commit: {len(app_files)} application file(s) in this commit — confirm "
        "scripts/dev/quality-gate.sh and an independent review (/review-diff) ran on this diff."}))
sys.exit(0)
