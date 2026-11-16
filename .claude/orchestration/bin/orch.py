#!/usr/bin/env python3
"""ERP orchestration queue + worktree manager (stdlib only).

Policy: .claude/orchestration/README.md. State lives in .claude/state/queue.json.

Commands
  status                         table of tasks
  validate                       schema, states, ownership conflicts, concurrency limits
  base-check                     approved base vs default branch vs session HEAD
  add  --id T-001 --title ... --agent erp-backend --owns a.py,b/ [--skills x,y]
       [--depends T-000] [--base SHA] [--target-branch orch/T-001] [--test-db NAME]
       --acceptance "criterion" [--acceptance ...] [--decisions OD-01,OD-10]
  check-conflicts ID             would ID collide with any active task?
  transition ID STATE [--note]   state machine (enforces deps/conflicts/limits/base)
  worktree create ID             pinned worktree from the task's base SHA (never from default branch)
  worktree verify ID             branch, HEAD ancestry, dirty files, edits outside owned files

Never removes worktrees, never pushes, never resets. Exit 0 ok, 1 rule violation, 2 usage error.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(os.environ.get("ORCH_REPO") or Path(__file__).resolve().parents[3])
QUEUE = Path(os.environ.get("ORCH_QUEUE") or REPO / ".claude/state/queue.json")
WORKTREE_ROOT = Path(os.environ.get("ORCH_WORKTREE_ROOT") or REPO / ".claude/worktrees")

STATES = ("pending", "ready", "running", "blocked", "review", "integration", "completed", "failed")
TRANSITIONS = {
    "pending": {"ready", "blocked", "failed"},
    "ready": {"running", "blocked", "pending"},
    "running": {"review", "blocked", "failed"},
    "blocked": {"pending", "ready"},
    "review": {"running", "integration", "failed"},
    "integration": {"completed", "failed", "running"},
    "failed": {"pending"},
    "completed": set(),
}
ACTIVE = {"running", "review", "integration"}  # states that hold file ownership
REVIEW_STATUSES = ("not-started", "in-review", "changes-requested", "approved")
TASK_ID = re.compile(r"^T-\d{3,}$")
REQUIRED = ("id", "title", "agent", "skills", "owned_files", "depends_on", "base_sha",
            "target_branch", "test_database", "acceptance_criteria", "review", "state")


class Violation(Exception):
    pass


# ---------------------------------------------------------------- io helpers
def now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd or REPO, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise Violation(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


@contextlib.contextmanager
def locked_queue(write: bool):
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    lock = open(str(QUEUE) + ".lock", "a+")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        q = json.loads(QUEUE.read_text()) if QUEUE.exists() else None
        if q is None:
            raise Violation(f"queue not found: {QUEUE}")
        yield q
        if write:
            q["updated"] = now()
            fd, tmp = tempfile.mkstemp(dir=QUEUE.parent, prefix=".queue.", suffix=".json")
            with os.fdopen(fd, "w") as f:
                json.dump(q, f, indent=2)
                f.write("\n")
            os.replace(tmp, QUEUE)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def task_of(q: dict, tid: str) -> dict:
    for t in q["tasks"]:
        if t["id"] == tid:
            return t
    raise Violation(f"unknown task {tid}")


def is_readonly(q: dict, agent: str) -> bool:
    return agent in q["agents"]["readonly"]


# ---------------------------------------------------------------- rules
def paths_overlap(a: str, b: str) -> bool:
    a, b = a.strip().lstrip("./"), b.strip().lstrip("./")
    if a == b:
        return True
    if any(ch in a for ch in "*?[") or any(ch in b for ch in "*?["):
        return fnmatch.fnmatch(a, b) or fnmatch.fnmatch(b, a) or fnmatch.fnmatch(a.rstrip("/") + "/x", b) \
            or fnmatch.fnmatch(b.rstrip("/") + "/x", a)
    if a.endswith("/") and b.startswith(a):
        return True
    if b.endswith("/") and a.startswith(b):
        return True
    return False


def conflicts(q: dict, cand: dict) -> list[str]:
    out = []
    for t in q["tasks"]:
        if t["id"] == cand["id"] or t["state"] not in ACTIVE:
            continue
        for a in cand["owned_files"]:
            for b in t["owned_files"]:
                if paths_overlap(a, b):
                    out.append(f"{cand['id']}:{a} <-> {t['id']}:{b} ({t['state']})")
    return out


def owned(path: str, owned_files: list[str]) -> bool:
    return any(paths_overlap(path, o) for o in owned_files)


def validate_task(q: dict, t: dict) -> list[str]:
    errs = [f"{t.get('id', '?')}: missing field {k}" for k in REQUIRED if k not in t]
    if errs:
        return errs
    tid = t["id"]
    if not TASK_ID.match(tid):
        errs.append(f"{tid}: id must match T-NNN")
    if t["state"] not in STATES:
        errs.append(f"{tid}: bad state {t['state']}")
    known = set(q["agents"]["implementation"]) | set(q["agents"]["readonly"])
    if t["agent"] not in known:
        errs.append(f"{tid}: unknown agent {t['agent']} (allowed: {sorted(known)})")
    if is_readonly(q, t["agent"]) and t["owned_files"]:
        errs.append(f"{tid}: read-only agent {t['agent']} cannot own files")
    if not is_readonly(q, t["agent"]) and not t["owned_files"] and t["state"] != "pending":
        errs.append(f"{tid}: implementation task needs explicit owned_files before leaving pending")
    if not t["acceptance_criteria"]:
        errs.append(f"{tid}: acceptance_criteria empty")
    if t["review"].get("status") not in REVIEW_STATUSES:
        errs.append(f"{tid}: review.status must be one of {REVIEW_STATUSES}")
    ids = {x["id"] for x in q["tasks"]}
    for d in t["depends_on"]:
        if d not in ids:
            errs.append(f"{tid}: depends on unknown task {d}")
        if d == tid:
            errs.append(f"{tid}: depends on itself")
    if t["base_sha"] and not re.fullmatch(r"[0-9a-f]{40}", t["base_sha"]):
        errs.append(f"{tid}: base_sha must be a full 40-char SHA")
    return errs


def validate_queue(q: dict) -> list[str]:
    errs = []
    for k in ("schema_version", "approved_base", "limits", "agents", "tasks", "history"):
        if k not in q:
            errs.append(f"queue: missing {k}")
    if errs:
        return errs
    seen = set()
    for t in q["tasks"]:
        if t.get("id") in seen:
            errs.append(f"duplicate task id {t.get('id')}")
        seen.add(t.get("id"))
        errs += validate_task(q, t)
    for t in q["tasks"]:
        if t.get("state") in ACTIVE:
            errs += [f"ownership conflict: {c}" for c in conflicts(q, t)]
    errs = list(dict.fromkeys(errs))
    impl = [t for t in q["tasks"] if t.get("state") == "running" and not is_readonly(q, t.get("agent", ""))]
    rev = [t for t in q["tasks"] if t.get("state") == "running" and is_readonly(q, t.get("agent", ""))]
    if len(impl) > q["limits"]["max_implementation_agents"]:
        errs.append(f"limit: {len(impl)} implementation agents running > {q['limits']['max_implementation_agents']}")
    if len(rev) > q["limits"]["max_readonly_reviewers"]:
        errs.append(f"limit: {len(rev)} reviewers running > {q['limits']['max_readonly_reviewers']}")
    # dependency cycles
    graph = {t["id"]: t.get("depends_on", []) for t in q["tasks"]}
    state: dict[str, int] = {}

    def visit(n: str, stack: tuple) -> None:
        if state.get(n) == 2:
            return
        if state.get(n) == 1:
            errs.append(f"dependency cycle: {' -> '.join(stack + (n,))}")
            return
        state[n] = 1
        for d in graph.get(n, []):
            visit(d, stack + (n,))
        state[n] = 2

    for n in graph:
        visit(n, ())
    return errs


# ---------------------------------------------------------------- worktrees
def default_branch() -> str:
    ref = git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False)
    return ref.replace("refs/remotes/origin/", "") if ref else "develop"


def worktree_path(t: dict) -> Path:
    return WORKTREE_ROOT / t["id"]


def verify_worktree(t: dict) -> list[str]:
    p = worktree_path(t)
    if not p.exists():
        return [f"{t['id']}: worktree missing at {p} (run: orch.py worktree create {t['id']})"]
    errs = []
    head = git("rev-parse", "HEAD", cwd=p)
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=p)
    if branch != t["target_branch"]:
        errs.append(f"{t['id']}: worktree on branch {branch}, expected {t['target_branch']}")
    r = subprocess.run(["git", "merge-base", "--is-ancestor", t["base_sha"], head], cwd=p)
    if r.returncode != 0:
        errs.append(f"{t['id']}: worktree HEAD {head[:10]} does not descend from approved base {t['base_sha'][:10]}")
    changed = set(filter(None, git("diff", "--name-only", t["base_sha"], cwd=p).splitlines()))
    changed |= set(filter(None, git("ls-files", "--others", "--exclude-standard", cwd=p).splitlines()))
    stray = sorted(f for f in changed if not owned(f, t["owned_files"]))
    if stray:
        errs.append(f"{t['id']}: files changed outside ownership: {', '.join(stray[:20])}")
    return errs


# ---------------------------------------------------------------- commands
def cmd_status(_a) -> int:
    with locked_queue(False) as q:
        b = q["approved_base"]
        print(f"approved base: {b['branch']} @ {b['sha'][:10]}   limits: impl={q['limits']['max_implementation_agents']}"
              f" reviewers={q['limits']['max_readonly_reviewers']}")
        if not q["tasks"]:
            print("(no tasks)")
        for t in q["tasks"]:
            print(f"{t['id']:7} {t['state']:12} {t['agent']:22} review={t['review']['status']:17} "
                  f"deps={','.join(t['depends_on']) or '-':10} {t['title']}")
    return 0


def cmd_validate(_a) -> int:
    with locked_queue(False) as q:
        errs = validate_queue(q)
    for e in errs:
        print("FAIL", e)
    print("queue OK" if not errs else f"{len(errs)} problem(s)")
    return 1 if errs else 0


def cmd_base_check(_a) -> int:
    with locked_queue(False) as q:
        base = q["approved_base"]
    head = git("rev-parse", "HEAD")
    cur = git("rev-parse", "--abbrev-ref", "HEAD")
    db = default_branch()
    db_sha = git("rev-parse", db, check=False) or "?"
    print(f"session HEAD     : {cur} @ {head[:10]}")
    print(f"approved base    : {base['branch']} @ {base['sha'][:10]}")
    print(f"default branch   : {db} @ {db_sha[:10]}")
    dirty = [l for l in git("status", "--porcelain").splitlines() if l]
    print(f"parent dirty     : {len(dirty)} uncommitted path(s) — NOT present in any new worktree")
    rc = 0
    if db_sha != base["sha"]:
        print("WARNING: default branch != approved base. Native `isolation: \"worktree\"` may branch from "
              f"{db}; use `orch.py worktree create <ID>` (pinned to the approved SHA) instead.")
    if subprocess.run(["git", "merge-base", "--is-ancestor", base["sha"], head], cwd=REPO).returncode != 0:
        print("FAIL: session HEAD does not contain the approved base")
        rc = 1
    return rc


def cmd_add(a) -> int:
    with locked_queue(True) as q:
        if any(t["id"] == a.id for t in q["tasks"]):
            raise Violation(f"task {a.id} exists")
        base = a.base or q["approved_base"]["sha"]
        base = git("rev-parse", "--verify", base + "^{commit}")
        t = {
            "id": a.id, "title": a.title, "agent": a.agent,
            "skills": [s for s in (a.skills or "").split(",") if s],
            "owned_files": [s for s in (a.owns or "").split(",") if s],
            "depends_on": [s for s in (a.depends or "").split(",") if s],
            "base_sha": base,
            "target_branch": a.target_branch or f"orch/{a.id}",
            "worktree": str(WORKTREE_ROOT.relative_to(REPO) / a.id) if WORKTREE_ROOT.is_relative_to(REPO) else str(WORKTREE_ROOT / a.id),
            "test_database": a.test_db or f"test_lm_{a.id.lower().replace('-', '_')}",
            "acceptance_criteria": a.acceptance or [],
            "decision_refs": [s for s in (a.decisions or "").split(",") if s],
            "review": {"status": "not-started", "reviewers": [], "findings": []},
            "state": "pending", "created": now(), "updated": now(), "notes": [],
        }
        errs = validate_task(q, t)
        if errs:
            raise Violation("; ".join(errs))
        q["tasks"].append(t)
        q["history"].append({"at": now(), "task": a.id, "event": "added"})
    print(f"added {a.id} (pending)")
    return 0


def cmd_check_conflicts(a) -> int:
    with locked_queue(False) as q:
        c = conflicts(q, task_of(q, a.id))
    for x in c:
        print("CONFLICT", x)
    print("no conflicts" if not c else f"{len(c)} conflict(s)")
    return 1 if c else 0


def cmd_transition(a) -> int:
    new = a.state
    if new not in STATES:
        raise Violation(f"unknown state {new}")
    with locked_queue(True) as q:
        t = task_of(q, a.id)
        old = t["state"]
        if new not in TRANSITIONS[old]:
            raise Violation(f"illegal transition {old} -> {new} (allowed: {sorted(TRANSITIONS[old])})")
        errs = validate_task(q, {**t, "state": new})
        if new in ("ready", "running"):
            for d in t["depends_on"]:
                if task_of(q, d)["state"] != "completed":
                    errs.append(f"dependency {d} not completed")
        if new in ACTIVE:
            errs += [f"ownership conflict: {c}" for c in conflicts(q, t)]
        if new == "running":
            ro = is_readonly(q, t["agent"])
            running = [x for x in q["tasks"] if x["state"] == "running" and x["id"] != t["id"]
                       and is_readonly(q, x["agent"]) == ro]
            lim = q["limits"]["max_readonly_reviewers" if ro else "max_implementation_agents"]
            if len(running) >= lim:
                errs.append(f"concurrency limit reached ({len(running)}/{lim} {'reviewers' if ro else 'implementation agents'})")
            if not ro:
                errs += verify_worktree(t)
        if new == "integration" and t["review"]["status"] != "approved":
            errs.append("review.status must be 'approved' before integration")
        if new == "completed" and not a.note:
            errs.append("completed requires --note with the gate/test evidence")
        if errs:
            raise Violation("; ".join(errs))
        t["state"] = new
        t["updated"] = now()
        if a.note:
            t["notes"].append({"at": now(), "note": a.note})
        q["history"].append({"at": now(), "task": t["id"], "event": f"{old}->{new}", "note": a.note or ""})
    print(f"{a.id}: {old} -> {new}")
    return 0


def cmd_review(a) -> int:
    with locked_queue(True) as q:
        t = task_of(q, a.id)
        if a.status not in REVIEW_STATUSES:
            raise Violation(f"review status must be one of {REVIEW_STATUSES}")
        t["review"]["status"] = a.status
        if a.reviewer and a.reviewer not in t["review"]["reviewers"]:
            t["review"]["reviewers"].append(a.reviewer)
        if a.note:
            t["review"]["findings"].append({"at": now(), "by": a.reviewer or "", "note": a.note})
        q["history"].append({"at": now(), "task": t["id"], "event": f"review:{a.status}", "note": a.note or ""})
    print(f"{a.id}: review -> {a.status}")
    return 0


def cmd_worktree(a) -> int:
    with locked_queue(a.action == "create") as q:
        t = task_of(q, a.id)
        if a.action == "verify":
            errs = verify_worktree(t)
            for e in errs:
                print("FAIL", e)
            print(f"{a.id}: worktree OK (base {t['base_sha'][:10]}, branch {t['target_branch']})" if not errs else "")
            return 1 if errs else 0
        if is_readonly(q, t["agent"]):
            raise Violation("read-only tasks review the integration tree; they get no worktree")
        p = worktree_path(t)
        if p.exists():
            raise Violation(f"{p} already exists — not touching it (verify with: orch.py worktree verify {a.id})")
        git("rev-parse", "--verify", t["base_sha"] + "^{commit}")
        if git("rev-parse", "--verify", "--quiet", "refs/heads/" + t["target_branch"], check=False):
            raise Violation(f"branch {t['target_branch']} already exists — choose another target_branch")
        db = default_branch()
        if git("rev-parse", db, check=False) != t["base_sha"]:
            print(f"note: default branch {db} differs from task base; pinning worktree to {t['base_sha'][:10]}")
        WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)
        git("worktree", "add", "-b", t["target_branch"], str(p), t["base_sha"])
        errs = verify_worktree(t)
        if errs:
            raise Violation("; ".join(errs))
        q["history"].append({"at": now(), "task": t["id"], "event": "worktree-created", "note": str(p)})
        print(f"{a.id}: worktree {p} on {t['target_branch']} @ {t['base_sha'][:10]} (verified)")
        print("reminder: parent-session uncommitted changes are NOT in this worktree")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("validate").set_defaults(fn=cmd_validate)
    sub.add_parser("base-check").set_defaults(fn=cmd_base_check)
    p = sub.add_parser("add")
    p.add_argument("--id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--owns")
    p.add_argument("--skills")
    p.add_argument("--depends")
    p.add_argument("--base")
    p.add_argument("--target-branch")
    p.add_argument("--test-db")
    p.add_argument("--decisions")
    p.add_argument("--acceptance", action="append")
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("check-conflicts")
    p.add_argument("id")
    p.set_defaults(fn=cmd_check_conflicts)
    p = sub.add_parser("transition")
    p.add_argument("id")
    p.add_argument("state")
    p.add_argument("--note")
    p.set_defaults(fn=cmd_transition)
    p = sub.add_parser("review")
    p.add_argument("id")
    p.add_argument("status")
    p.add_argument("--reviewer")
    p.add_argument("--note")
    p.set_defaults(fn=cmd_review)
    p = sub.add_parser("worktree")
    p.add_argument("action", choices=("create", "verify"))
    p.add_argument("id")
    p.set_defaults(fn=cmd_worktree)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except Violation as e:
        print(f"REJECTED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
