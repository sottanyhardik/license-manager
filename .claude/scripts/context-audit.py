#!/usr/bin/env python3
"""ERP context loader — the smallest correct reading list for the current change (read-only, offline).

Usage:
  python3 .claude/scripts/context-audit.py                 # working tree vs HEAD (+ untracked)
  python3 .claude/scripts/context-audit.py --base develop  # committed range base..HEAD + working tree
  python3 .claude/scripts/context-audit.py --files backend/apps/license/services/balance_calculator.py

Prints, compactly: changed files by area; for each source file its dependents (blast radius, from
.claude/index/dependents.tsv) and related tests; whether the canonical CIF business-rule paths are touched (→ read
.claude/rules/business-rules.md in full and run cif-balance-auditor — never rely on summaries); migrations; and
decision records mentioning the touched modules. It never reads file contents into the output.
"""
from __future__ import annotations

import argparse
import collections
import fnmatch
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUSINESS_RULE_GLOBS = [
    "backend/apps/license/**", "backend/apps/allotment/**", "backend/apps/bill_of_entry/**", "backend/apps/trade/**",
    "backend/apps/reconciliation/**", "backend/apps/core/**", "frontend/src/**/*[Bb]alance*", "frontend/src/**/*[Ll]edger*",
]
FINANCIAL_HINTS = ("balance", "ledger", "cif", "boe", "allot", "invoice", "trade", "reconcil", "plan")


def _git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout
    return [line for line in out.splitlines() if line.strip()]


def changed_files(base: str | None) -> list[str]:
    files = set(_git("diff", "--name-only", "HEAD")) | set(_git("ls-files", "--others", "--exclude-standard"))
    if base:
        files |= set(_git("diff", "--name-only", f"{base}...HEAD"))
    return sorted(f for f in files if not f.endswith(".DS_Store"))


def load_dependents() -> dict[str, list[str]]:
    deps: dict[str, list[str]] = collections.defaultdict(list)
    path = ROOT / ".claude/index/dependents.tsv"
    if path.exists():
        for line in path.read_text().splitlines()[1:]:
            if "\t" in line:
                src, dep = line.split("\t", 1)
                deps[src].append(dep)
    return deps


def area(path: str) -> str:
    parts = path.split("/")
    if parts[0] == "backend" and len(parts) > 2 and parts[1] == "apps":
        return f"backend/{parts[2]}"
    if parts[0] == "frontend" and len(parts) > 3:
        return "frontend/" + "/".join(parts[2:4])
    return parts[0] if len(parts) > 1 else "(root)"


def is_test(path: str) -> bool:
    name = Path(path).name
    return "/tests/" in path or name.startswith("test_") or ".test." in name or ".spec." in name


def related_tests(path: str, deps: dict[str, list[str]]) -> list[str]:
    tests = {d for d in deps.get(path, []) if is_test(d)}
    stem = Path(path).stem.replace(".test", "")
    for candidate in (Path(path).with_name(f"{stem}.test.tsx"), Path(path).with_name(f"{stem}.test.ts")):
        if (ROOT / candidate).exists():
            tests.add(str(candidate))
    if path.startswith("backend/"):
        app_tests = ROOT / Path(*Path(path).parts[:3]) / "tests"
        if app_tests.is_dir():
            tests |= {str(p.relative_to(ROOT)) for p in app_tests.glob(f"test_*{stem}*.py")}
    return sorted(tests)


def decisions_for(stems: set[str]) -> list[str]:
    hits = []
    for doc in sorted((ROOT / "docs/decisions").glob("*.md")):
        text = doc.read_text(errors="ignore").lower()
        if any(s.lower() in text for s in stems if len(s) > 5):
            hits.append(str(doc.relative_to(ROOT)))
    return hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--max-dependents", type=int, default=8)
    args = ap.parse_args()
    files = args.files or changed_files(args.base)
    if not files:
        print("No changed files.")
        return
    deps = load_dependents()
    by_area = collections.defaultdict(list)
    for f in files:
        by_area[area(f)].append(f)
    print(f"Changed files: {len(files)}")
    for a, fs in sorted(by_area.items()):
        print(f"  {a}: {len(fs)}  " + ", ".join(Path(f).name for f in fs[:8]) + (" …" if len(fs) > 8 else ""))
    business = [f for f in files if any(fnmatch.fnmatch(f, g) for g in BUSINESS_RULE_GLOBS) and not is_test(f)]
    financial = [f for f in business if any(h in f.lower() for h in FINANCIAL_HINTS)]
    print(f"\nBusiness-rule paths touched: {len(business)}" + (" → business-rules.md applies (read it in full before changing them)" if business else "")
          + ("; balance/ledger/CIF-like files below → cif-balance-auditor review required" if financial else ""))
    for f in financial[:20]:
        print(f"  ! {f}")
    migrations = [f for f in files if "/migrations/" in f]
    if migrations:
        print(f"\nMigrations: {', '.join(migrations)} → migration-safety skill; makemigrations --check")
    print("\nBlast radius + related tests (source files):")
    for f in files:
        if is_test(f) or not f.endswith((".py", ".ts", ".tsx")):
            continue
        d = [x for x in deps.get(f, []) if not is_test(x)]
        t = related_tests(f, deps)
        print(f"  {f}\n    dependents {len(d)}: {', '.join(d[:args.max_dependents])}{' …' if len(d) > args.max_dependents else ''}"
              f"\n    tests: {', '.join(t) or '— (none found: add or locate tests)'}")
    stems = {Path(f).stem for f in files if not is_test(f)}
    docs = decisions_for(stems)
    if docs:
        print("\nDecision records mentioning these modules (reuse, do not rediscover):\n  " + "\n  ".join(docs))


if __name__ == "__main__":
    main()
