#!/usr/bin/env python3
"""pip-audit gate: fail on any known vulnerability not covered by an unexpired exception.

Usage:
    python scripts/security/pip_audit_gate.py --scope backend  -r backend/requirements.txt
    python scripts/security/pip_audit_gate.py --scope mds      -r master-data-service/requirements-prod.txt

Exit codes: 0 = no unexcepted findings; 1 = unexcepted findings or expired/invalid
exceptions; 2 = pip-audit itself failed to run (never treated as a pass).

Findings are never suppressed silently: excepted findings are still printed (marked
EXCEPTED with reason + expiry). Exceptions live in scripts/security/pip-audit-exceptions.json
(format documented in docs/erp-transformation/dependency-register.md). Stdlib only.
"""
import argparse
import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_EXCEPTIONS = Path(__file__).with_name("pip-audit-exceptions.json")


def load_exceptions(path, scope, today):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    active, problems = [], []
    for e in data.get("exceptions", []):
        missing = [k for k in ("id", "package", "reason", "expires") if not e.get(k)]
        if missing:
            problems.append(f"exception {e.get('id', '?')}: missing {missing}")
            continue
        try:
            expires = datetime.date.fromisoformat(e["expires"])
        except ValueError:
            problems.append(f"exception {e['id']}: bad expires {e['expires']!r} (want YYYY-MM-DD)")
            continue
        if scope not in e.get("scopes", [scope]):
            continue
        if expires < today:
            problems.append(f"exception {e['id']} ({e['package']}) EXPIRED on {e['expires']}")
            continue
        active.append(e)
    return active, problems


def run_pip_audit(requirement):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out = tmp.name
    cmd = [sys.executable, "-m", "pip_audit", "-r", requirement, "--format", "json", "-o", out]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        report = json.loads(Path(out).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        sys.stderr.write(proc.stdout + proc.stderr)
        sys.exit(2)  # tool failure is not a pass
    finally:
        Path(out).unlink(missing_ok=True)
    return report


def collect(report):
    """Deduplicate: pip-audit can report one advisory from several sources."""
    findings = []
    for dep in report.get("dependencies", []):
        for v in dep.get("vulns", []):
            ids = {v["id"], *v.get("aliases", [])}
            for f in findings:
                if f["package"] == dep["name"] and f["version"] == dep["version"] and f["ids"] & ids:
                    f["ids"] |= ids
                    f["fix"] |= set(v.get("fix_versions", []))
                    break
            else:
                findings.append({"package": dep["name"], "version": dep["version"], "ids": set(ids),
                                 "fix": set(v.get("fix_versions", []))})
    return findings


def label(ids):
    return sorted(ids, key=lambda i: (i.startswith("BIT-"), not i.startswith("CVE-"), i))[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-r", "--requirement", required=True)
    ap.add_argument("--scope", required=True, help="exceptions scope tag, e.g. backend | mds")
    ap.add_argument("--exceptions", default=str(DEFAULT_EXCEPTIONS))
    ap.add_argument("--report", help="use an existing pip-audit JSON report instead of running pip-audit")
    args = ap.parse_args()

    active, problems = load_exceptions(args.exceptions, args.scope, datetime.date.today())
    report = json.loads(Path(args.report).read_text()) if args.report else run_pip_audit(args.requirement)
    findings = collect(report)

    unexcepted, excepted = [], []
    for f in findings:
        match = next((e for e in active if e["package"].lower() == f["package"].lower()
                      and ({e["id"], *e.get("aliases", [])} & f["ids"])), None)
        (excepted if match else unexcepted).append((f, match))

    print(f"pip-audit [{args.scope}] {args.requirement}: {len(findings)} unique advisories, "
          f"{len(excepted)} excepted, {len(unexcepted)} NOT excepted")
    for status, rows in (("UNEXCEPTED", unexcepted), ("EXCEPTED", excepted)):
        for f, e in sorted(rows, key=lambda r: (r[0]["package"], sorted(r[0]["ids"])[0])):
            extra = f" reason={e['reason']!r} expires={e['expires']}" if e else ""
            print(f"  {status:10} {f['package']}=={f['version']} {label(f['ids'])} "
                  f"fix={','.join(sorted(f['fix'])) or 'none'}{extra}")
    for p in problems:
        print("  EXCEPTION-FILE PROBLEM:", p)
    return 1 if (unexcepted or problems) else 0


if __name__ == "__main__":
    sys.exit(main())
