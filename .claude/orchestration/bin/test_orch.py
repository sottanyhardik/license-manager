#!/usr/bin/env python3
"""Self-test for orch.py against a throwaway git repo in $TMPDIR.

Run: python3 .claude/orchestration/bin/test_orch.py
Never touches the real repository or .claude/state/queue.json.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORCH = HERE / "orch.py"


def sh(*args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class OrchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orch-test-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        sh("git", "init", "-q", "-b", "develop", cwd=self.repo)
        sh("git", "config", "user.email", "t@example.com", cwd=self.repo)
        sh("git", "config", "user.name", "t", cwd=self.repo)
        (self.repo / "a.py").write_text("a\n")
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg" / "b.py").write_text("b\n")
        sh("git", "add", ".", cwd=self.repo)
        sh("git", "commit", "-qm", "init", cwd=self.repo)
        self.develop_sha = sh("git", "rev-parse", "HEAD", cwd=self.repo)
        # feature branch ahead of develop = the "approved base"
        sh("git", "checkout", "-qb", "feature/x", cwd=self.repo)
        (self.repo / "a.py").write_text("a2\n")
        sh("git", "commit", "-qam", "feature", cwd=self.repo)
        self.base = sh("git", "rev-parse", "HEAD", cwd=self.repo)
        self.queue = self.tmp / "queue.json"
        real = json.loads((HERE.parents[1] / "state" / "queue.json").read_text())
        real["approved_base"] = {"branch": "feature/x", "sha": self.base, "recorded": "test"}
        real["tasks"], real["history"] = [], []
        self.queue.write_text(json.dumps(real))
        self.env = {**os.environ, "ORCH_REPO": str(self.repo), "ORCH_QUEUE": str(self.queue),
                    "ORCH_WORKTREE_ROOT": str(self.tmp / "wt")}

    def tearDown(self):
        subprocess.run(["git", "worktree", "list"], cwd=self.repo, capture_output=True)
        shutil.rmtree(self.tmp, ignore_errors=True)  # temp dir only

    def orch(self, *args):
        return subprocess.run([sys.executable, str(ORCH), *args], cwd=self.repo, env=self.env,
                              capture_output=True, text=True)

    def add(self, tid, agent="erp-backend", owns="a.py", depends=None):
        args = ["add", "--id", tid, "--title", tid, "--agent", agent, "--acceptance", "works"]
        if owns:
            args += ["--owns", owns]
        if depends:
            args += ["--depends", depends]
        r = self.orch(*args)
        self.assertEqual(r.returncode, 0, r.stderr)

    def start(self, tid):
        for step in (["transition", tid, "ready"], ["worktree", "create", tid], ["transition", tid, "running"]):
            r = self.orch(*step)
            self.assertEqual(r.returncode, 0, f"{step}: {r.stdout}{r.stderr}")

    # ---------------------------------------------------------------- tests
    def test_worktree_pinned_to_base_not_default_branch(self):
        self.add("T-001")
        self.start("T-001")
        wt = self.tmp / "wt" / "T-001"
        self.assertEqual(sh("git", "rev-parse", "HEAD", cwd=wt), self.base)
        self.assertNotEqual(self.base, self.develop_sha)
        self.assertEqual((wt / "a.py").read_text(), "a2\n")  # feature content, not develop

    def test_ownership_conflict_rejected(self):
        self.add("T-001", owns="a.py")
        self.add("T-002", owns="a.py")
        self.start("T-001")
        self.orch("transition", "T-002", "ready")
        self.assertEqual(self.orch("check-conflicts", "T-002").returncode, 1)
        self.orch("worktree", "create", "T-002")
        r = self.orch("transition", "T-002", "running")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ownership conflict", r.stderr)

    def test_directory_ownership_overlaps_file(self):
        self.add("T-001", owns="pkg/")
        self.add("T-002", owns="pkg/b.py")
        self.start("T-001")
        self.assertEqual(self.orch("check-conflicts", "T-002").returncode, 1)

    def test_concurrency_limit(self):
        for i in range(1, 6):
            self.add(f"T-00{i}", owns=f"f{i}.py")
        for i in range(1, 5):
            self.start(f"T-00{i}")
        self.orch("transition", "T-005", "ready")
        self.orch("worktree", "create", "T-005")
        r = self.orch("transition", "T-005", "running")
        self.assertEqual(r.returncode, 1)
        self.assertIn("concurrency limit", r.stderr)

    def test_dependency_must_complete(self):
        self.add("T-001")
        self.add("T-002", owns="pkg/b.py", depends="T-001")
        r = self.orch("transition", "T-002", "ready")
        self.assertEqual(r.returncode, 1)
        self.assertIn("dependency T-001 not completed", r.stderr)

    def test_edit_outside_ownership_detected(self):
        self.add("T-001", owns="a.py")
        self.start("T-001")
        wt = self.tmp / "wt" / "T-001"
        (wt / "pkg" / "b.py").write_text("stray\n")
        r = self.orch("worktree", "verify", "T-001")
        self.assertEqual(r.returncode, 1)
        self.assertIn("outside ownership", r.stdout)

    def test_readonly_agent_cannot_own_files_or_get_worktree(self):
        r = self.orch("add", "--id", "T-001", "--title", "x", "--agent", "erp-reviewer",
                      "--owns", "a.py", "--acceptance", "x")
        self.assertEqual(r.returncode, 1)
        self.add("T-002", agent="erp-reviewer", owns=None)
        self.assertEqual(self.orch("worktree", "create", "T-002").returncode, 1)

    def test_illegal_transition_and_review_gate(self):
        self.add("T-001")
        self.assertEqual(self.orch("transition", "T-001", "completed").returncode, 1)
        self.start("T-001")
        self.assertEqual(self.orch("transition", "T-001", "review").returncode, 0)
        r = self.orch("transition", "T-001", "integration")
        self.assertEqual(r.returncode, 1)
        self.assertIn("approved", r.stderr)
        self.orch("review", "T-001", "approved", "--reviewer", "erp-reviewer")
        self.assertEqual(self.orch("transition", "T-001", "integration").returncode, 0)
        self.assertEqual(self.orch("transition", "T-001", "completed").returncode, 1)  # needs --note
        self.assertEqual(self.orch("transition", "T-001", "completed", "--note", "gate PASS").returncode, 0)

    def test_existing_worktree_never_overwritten(self):
        self.add("T-001")
        self.start("T-001")
        marker = self.tmp / "wt" / "T-001" / "keep.txt"
        marker.write_text("keep")
        self.assertEqual(self.orch("worktree", "create", "T-001").returncode, 1)
        self.assertTrue(marker.exists())

    def test_validate_and_base_check(self):
        self.assertEqual(self.orch("validate").returncode, 0)
        r = self.orch("base-check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("default branch", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
