#!/usr/bin/env python3
"""Self-test for post_edit_validate.py, pre_commit_check.py and stop_verify_reminder.py.

Run: python3 .claude/hooks/test_hooks.py
Uses throwaway temp files / a throwaway git repo under $TMPDIR only — never touches this repo.
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
fails = 0


def run(script, payload, cwd=None, env=None):
    p = subprocess.run([sys.executable, os.path.join(HERE, script)], input=json.dumps(payload),
                       capture_output=True, text=True, cwd=cwd, env=env, timeout=20)
    return p.returncode, p.stdout, p.stderr


def check(name, cond):
    global fails
    print(("ok   " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


with tempfile.TemporaryDirectory() as d:
    # --- post_edit_validate -------------------------------------------------
    good, bad = os.path.join(d, "good.py"), os.path.join(d, "bad.py")
    open(good, "w").write("x = 1\n")
    open(bad, "w").write("def f(:\n")
    goodj, badj = os.path.join(d, "a.json"), os.path.join(d, "b.json")
    open(goodj, "w").write('{"a": 1}')
    open(badj, "w").write('{"a": ')
    tsconf = os.path.join(d, "tsconfig.json")
    open(tsconf, "w").write('{ // jsonc comment\n "a": 1 }')
    for path, want in [(good, 0), (bad, 2), (goodj, 0), (badj, 2), (tsconf, 0),
                       (os.path.join(d, "missing.py"), 0)]:
        rc, _, _ = run("post_edit_validate.py", {"tool_input": {"file_path": path}})
        check(f"post_edit_validate {os.path.basename(path)} -> {want}", rc == want)

    # --- pre_commit_check (throwaway repo) ----------------------------------
    repo = os.path.join(d, "repo")
    os.makedirs(os.path.join(repo, "backend"))
    g = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True)
    g("init", "-q"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
    open(os.path.join(repo, "README"), "w").write("x\n")
    g("add", "README"); g("commit", "-qm", "init")

    pc = lambda cmd: run("pre_commit_check.py", {"tool_input": {"command": cmd}}, cwd=repo)
    check("pre_commit non-commit command ignored", pc("git status")[0] == 0)

    open(os.path.join(repo, "backend", "ok.py"), "w").write("y = 2\n")
    g("add", "backend/ok.py")
    rc, out, _ = pc("git commit -m ok")
    check("pre_commit clean app commit allowed + reminder", rc == 0 and "systemMessage" in out)

    open(os.path.join(repo, "backend", "broken.py"), "w").write("def f(:\n")
    g("add", "backend/broken.py")
    check("pre_commit python syntax error blocked", pc("git commit -m x")[0] == 2)
    g("rm", "-q", "--cached", "backend/broken.py")

    secret_name = ".env"
    open(os.path.join(repo, secret_name), "w").write("A=1\n")
    g("add", "-f", secret_name)
    check("pre_commit secret file blocked", pc("git commit -m x")[0] == 2)
    g("rm", "-q", "--cached", secret_name)

    open(os.path.join(repo, "conf.txt"), "w").write("token = gh" + "p_" + "A" * 36 + "\n")
    g("add", "conf.txt")
    rc, _, err = pc("git commit -m x")
    check("pre_commit token in diff blocked (value not echoed)", rc == 2 and "A" * 20 not in err)
    g("rm", "-q", "--cached", "conf.txt")

    # --- stop_verify_reminder (dedupe) --------------------------------------
    env = dict(os.environ, CLAUDE_PROJECT_DIR=repo)
    payload = {"session_id": "selftest-" + str(os.getpid())}
    rc1, out1, _ = run("stop_verify_reminder.py", payload, env=env)
    rc2, out2, _ = run("stop_verify_reminder.py", payload, env=env)
    check("stop reminder fires once when app files change", rc1 == 0 and "systemMessage" in out1)
    check("stop reminder deduplicated on unchanged diff", rc2 == 0 and out2.strip() == "")
    rc3, out3, _ = run("stop_verify_reminder.py", dict(payload, stop_hook_active=True), env=env)
    check("stop reminder silent when stop_hook_active", rc3 == 0 and out3.strip() == "")
    marker = os.path.join(tempfile.gettempdir(), f"lm-claude-stop-{payload['session_id']}")
    if os.path.exists(marker):
        os.remove(marker)

print(f"\n{'ALL PASSED' if not fails else str(fails) + ' FAILED'}")
sys.exit(1 if fails else 0)
