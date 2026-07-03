#!/usr/bin/env python3
"""
Incremental code indexer for the License Manager repo.

Builds a compact, grep-friendly map of the codebase so Claude can locate code
without re-reading every source file. Deterministic (no LLM), stdlib-only, fast.

Outputs (all under .claude/index/):
  - manifest.json  : per-file {sha, size, lang, symbols} — change-detection + cache
  - symbols.tsv    : symbol <TAB> kind <TAB> file <TAB> line  — grep this to find code
  - CODE_MAP.md    : human/AI overview (dir tree + per-file symbol summary)

Usage:
  build_index.py               # full reconcile against git ls-files (incremental via sha)
  build_index.py --file PATH   # update a single file (used by the edit hook)
  build_index.py --file A --file B ...

Only files whose sha256 changed are re-parsed; everything else is reused from the
manifest, so a full run over a clean tree is nearly instantaneous.
"""

import json
import os
import re
import subprocess
import sys
import hashlib
from datetime import datetime, timezone

# --- locate repo root via git -------------------------------------------------

def repo_root():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        # fall back: two levels up from this file (.claude/index/ -> repo)
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = repo_root()
INDEX_DIR = os.path.join(ROOT, ".claude", "index")
MANIFEST = os.path.join(INDEX_DIR, "manifest.json")
SYMBOLS_TSV = os.path.join(INDEX_DIR, "symbols.tsv")
CODE_MAP = os.path.join(INDEX_DIR, "CODE_MAP.md")
IMPORTS_TSV = os.path.join(INDEX_DIR, "imports.tsv")
DEPENDENTS_TSV = os.path.join(INDEX_DIR, "dependents.tsv")

# Extensions we extract symbols from vs. merely list.
SYMBOL_EXT = {".py", ".js", ".jsx", ".ts", ".tsx"}
LIST_EXT = {".sh", ".sql", ".html", ".css", ".scss", ".less", ".vue"}
LANG = {
    ".py": "python", ".js": "js", ".jsx": "jsx", ".ts": "ts", ".tsx": "tsx",
    ".sh": "shell", ".sql": "sql", ".html": "html", ".css": "css",
    ".scss": "scss", ".less": "less", ".vue": "vue",
}
INDEXED_EXT = SYMBOL_EXT | LIST_EXT

# --- symbol extractors --------------------------------------------------------

PY_CLASS = re.compile(r"^class\s+(\w+)\s*(?:\(([^)]*)\))?")
PY_DEF = re.compile(r"^(?:async\s+)?def\s+(\w+)")
PY_METHOD = re.compile(r"^\s+(?:async\s+)?def\s+(\w+)")
PY_ROUTE = re.compile(r"\b(?:re_)?path\(\s*[rf]?['\"]([^'\"]*)['\"]")
PY_DRF_ROUTER = re.compile(r"\.register\(\s*[rf]?['\"]([^'\"]*)['\"]")


def extract_python(text):
    syms = []
    for i, line in enumerate(text.splitlines(), 1):
        m = PY_CLASS.match(line)
        if m:
            base = (m.group(2) or "").strip()
            kind = "class"
            if "models.Model" in base or "Model" in base:
                kind = "model"
            elif "Serializer" in base:
                kind = "serializer"
            elif any(b in base for b in ("APIView", "ViewSet", "View", "generics.")):
                kind = "view"
            elif "TestCase" in base or "TestCase" in m.group(1) or m.group(1).startswith("Test"):
                kind = "test"
            syms.append((m.group(1), kind, i))
            continue
        m = PY_DEF.match(line)
        if m:
            syms.append((m.group(1), "func", i))
            continue
        m = PY_METHOD.match(line)
        if m:
            # indented def -> class method / nested helper; still worth locating
            syms.append((m.group(1), "method", i))
            continue
        m = PY_ROUTE.search(line)
        if m:
            syms.append((m.group(1) or "/", "route", i))
            continue
        m = PY_DRF_ROUTER.search(line)
        if m:
            syms.append((m.group(1), "route", i))
    return syms


JS_EXPORT_FN = re.compile(r"^export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)")
JS_EXPORT_CONST = re.compile(r"^export\s+(?:default\s+)?const\s+(\w+)")
JS_EXPORT_CLASS = re.compile(r"^export\s+(?:default\s+)?class\s+(\w+)")
JS_FN = re.compile(r"^(?:async\s+)?function\s+(\w+)")
JS_CONST_FN = re.compile(r"^const\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>")
JS_CLASS = re.compile(r"^class\s+(\w+)")
JS_ROUTE = re.compile(r"(?:path|Route)\s*[:=]?\s*['\"]([^'\"]+)['\"]")


def _js_kind(name):
    # Capitalized -> likely a React component; use-prefixed -> hook.
    if name.startswith("use") and len(name) > 3 and name[3].isupper():
        return "hook"
    if name[:1].isupper():
        return "component"
    return "func"


def extract_js(text):
    syms = []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.rstrip()
        for pat, exported in ((JS_EXPORT_FN, True), (JS_EXPORT_CLASS, True),
                              (JS_EXPORT_CONST, True), (JS_FN, False),
                              (JS_CLASS, False), (JS_CONST_FN, False)):
            m = pat.match(s)
            if m:
                name = m.group(1)
                kind = "class" if "class" in pat.pattern else _js_kind(name)
                if exported:
                    kind = "export:" + kind
                syms.append((name, kind, i))
                break
    return syms


def extract_symbols(rel, text):
    ext = os.path.splitext(rel)[1].lower()
    if ext == ".py":
        return extract_python(text)
    if ext in (".js", ".jsx", ".ts", ".tsx"):
        return extract_js(text)
    return []  # LIST_EXT: tracked, no symbols


# --- import extraction (for the dependency graph) -----------------------------

PY_IMPORT = re.compile(r"^\s*import\s+([\w][\w.]*)")
PY_FROM = re.compile(r"^\s*from\s+(\.*[\w.]*)\s+import\b")
JS_FROM = re.compile(r"""from\s+['"]([^'"]+)['"]""")
JS_SIDE = re.compile(r"""^\s*import\s+['"]([^'"]+)['"]""")
JS_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]""")
JS_DYN = re.compile(r"""(?<![.\w])import\(\s*['"]([^'"]+)['"]""")


def extract_imports(rel, text):
    """Return the raw import specifiers found in a file (deduped, ordered)."""
    ext = os.path.splitext(rel)[1].lower()
    specs = []
    if ext == ".py":
        for line in text.splitlines():
            m = PY_FROM.match(line)
            if m:
                specs.append(m.group(1))
                continue
            m = PY_IMPORT.match(line)
            if m:
                specs.append(m.group(1))
    elif ext in (".js", ".jsx", ".ts", ".tsx"):
        for line in text.splitlines():
            for pat in (JS_FROM, JS_SIDE, JS_REQUIRE, JS_DYN):
                m = pat.search(line)
                if m:
                    specs.append(m.group(1))
    seen, out = set(), []
    for s in specs:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


# --- import resolution (raw specifier -> tracked repo file) -------------------

JS_EXTS = [".tsx", ".ts", ".jsx", ".js"]


def resolve_py(spec, from_rel, pyset):
    parts_dir = from_rel.split("/")[:-1]
    if spec.startswith("."):
        level = len(spec) - len(spec.lstrip("."))
        remainder = spec[level:]
        base = parts_dir[: len(parts_dir) - (level - 1)] if level >= 1 else parts_dir
        comps = base + (remainder.split(".") if remainder else [])
        cand = "/".join(comps)
        for c in (cand + ".py", cand + "/__init__.py"):
            if c in pyset:
                return c
        return None
    comps = spec.split(".")
    for cut in (len(comps), len(comps) - 1):
        if cut < 1:
            break
        sub = "/".join(comps[:cut])
        for prefix in ("backend/", ""):
            for suff in (".py", "/__init__.py"):
                c = prefix + sub + suff
                if c in pyset:
                    return c
    return None


def resolve_js(spec, from_rel, jsset):
    if spec.startswith("@/"):
        base = "frontend/src/" + spec[2:]
    elif spec.startswith("."):
        comps = from_rel.split("/")[:-1]
        for part in spec.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                comps = comps[:-1]
            else:
                comps.append(part)
        base = "/".join(comps)
    else:
        return None  # bare specifier -> external package
    cands = []
    _, ext = os.path.splitext(base)
    if ext:
        cands.append(base)
    cands += [base + e for e in JS_EXTS]
    cands += [base + "/index" + e for e in JS_EXTS]
    for c in cands:
        if c in jsset:
            return c
    return None


def build_dep_graph(files):
    """Return (forward, reverse): rel -> sorted list of internal rel targets."""
    pyset = {r for r in files if r.endswith(".py")}
    jsset = {r for r in files if os.path.splitext(r)[1].lower() in (".js", ".jsx", ".ts", ".tsx")}
    forward = {}
    reverse = {}
    for rel, info in files.items():
        ext = os.path.splitext(rel)[1].lower()
        targets = set()
        for spec in info.get("imports", []):
            if ext == ".py":
                t = resolve_py(spec, rel, pyset)
            elif ext in (".js", ".jsx", ".ts", ".tsx"):
                t = resolve_js(spec, rel, jsset)
            else:
                t = None
            if t and t != rel:
                targets.add(t)
        forward[rel] = sorted(targets)
        for t in targets:
            reverse.setdefault(t, set()).add(rel)
    reverse = {k: sorted(v) for k, v in reverse.items()}
    return forward, reverse

# --- git + hashing ------------------------------------------------------------

def git_files():
    out = subprocess.run(
        ["git", "-C", ROOT, "ls-files"],
        capture_output=True, text=True, check=True,
    )
    files = []
    for rel in out.stdout.splitlines():
        ext = os.path.splitext(rel)[1].lower()
        if ext in INDEXED_EXT:
            files.append(rel)
    return files


def sha_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

# --- manifest -----------------------------------------------------------------

def load_manifest():
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST) as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": 1, "files": {}}


def index_file(rel, manifest):
    """Re-parse rel if its sha changed; return True if the entry changed."""
    abspath = os.path.join(ROOT, rel)
    if not os.path.exists(abspath):
        return manifest["files"].pop(rel, None) is not None
    try:
        sha = sha_of(abspath)
    except Exception:
        return False
    prev = manifest["files"].get(rel)
    if prev and prev.get("sha") == sha:
        return False  # unchanged, reuse cached symbols
    ext = os.path.splitext(rel)[1].lower()
    symbols = []
    imports = []
    if ext in SYMBOL_EXT:
        try:
            with open(abspath, encoding="utf-8", errors="replace") as f:
                text = f.read()
            symbols = extract_symbols(rel, text)
            imports = extract_imports(rel, text)
        except Exception:
            symbols, imports = [], []
    manifest["files"][rel] = {
        "sha": sha,
        "size": os.path.getsize(abspath),
        "lang": LANG.get(ext, ext.lstrip(".")),
        "symbols": symbols,
        "imports": imports,
    }
    return True

# --- output rendering ---------------------------------------------------------

def render_outputs(manifest):
    files = manifest["files"]

    # symbols.tsv — the grep target
    tsv_lines = ["symbol\tkind\tfile\tline"]
    for rel in sorted(files):
        for name, kind, line in files[rel].get("symbols", []):
            tsv_lines.append(f"{name}\t{kind}\t{rel}\t{line}")
    with open(SYMBOLS_TSV, "w") as f:
        f.write("\n".join(tsv_lines) + "\n")

    # dependency graph -> imports.tsv (forward) + dependents.tsv (reverse)
    forward, reverse = build_dep_graph(files)
    imp_lines = ["file\timports"]
    for rel in sorted(forward):
        for t in forward[rel]:
            imp_lines.append(f"{rel}\t{t}")
    with open(IMPORTS_TSV, "w") as f:
        f.write("\n".join(imp_lines) + "\n")
    dep_lines = ["file\tdependent"]
    for rel in sorted(reverse):
        for d in reverse[rel]:
            dep_lines.append(f"{rel}\t{d}")
    with open(DEPENDENTS_TSV, "w") as f:
        f.write("\n".join(dep_lines) + "\n")

    # CODE_MAP.md — grouped by top-level dir
    groups = {}
    for rel in files:
        top = rel.split("/")[0] if "/" in rel else "(root)"
        groups.setdefault(top, []).append(rel)

    total_sym = sum(len(v.get("symbols", [])) for v in files.values())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    out = []
    out.append("# CODE MAP — auto-generated, do not hand-edit")
    out.append("")
    out.append(f"> Generated {now} · {len(files)} files · {total_sym} symbols")
    out.append("> Maintained by `.claude/index/build_index.py` (see README.md).")
    out.append("")
    out.append("## How to use this (for Claude)")
    out.append("")
    out.append("1. To find where a symbol/class/function/route/component lives, "
               "`grep` **`.claude/index/symbols.tsv`** (format: `symbol<TAB>kind<TAB>file<TAB>line`).")
    out.append("2. **Blast radius before changing a file** — `grep '^path/to/file' "
               "`.claude/index/dependents.tsv`` lists every file that imports it. "
               "`imports.tsv` is the forward direction (what a file depends on).")
    out.append("3. Use this map to see a file's shape before opening it; read source "
               "only for the specific file+line you need.")
    out.append("4. This file is refreshed automatically on every edit and at session "
               "start — trust it as current.")
    out.append("")
    dep_counts = sorted(
        ((len(v), k) for k, v in reverse.items()), reverse=True
    )[:25]
    if dep_counts:
        out.append("## Most-depended-on files (refactor risk — change with care)")
        out.append("")
        for n, rel in dep_counts:
            out.append(f"- `{rel}` — {n} dependents")
        out.append("")
    out.append("## Files by area")
    out.append("")
    for top in sorted(groups):
        rels = sorted(groups[top])
        gsym = sum(len(files[r].get("symbols", [])) for r in rels)
        out.append(f"### {top}/  ({len(rels)} files, {gsym} symbols)")
        out.append("")
        for rel in rels:
            info = files[rel]
            syms = info.get("symbols", [])
            if syms:
                # compact: up to 12 named symbols, prefer classes/components/routes
                names = [s[0] for s in syms][:12]
                extra = f" +{len(syms) - 12} more" if len(syms) > 12 else ""
                out.append(f"- `{rel}` — {', '.join(names)}{extra}")
            else:
                out.append(f"- `{rel}` [{info.get('lang','')}]")
        out.append("")
    with open(CODE_MAP, "w") as f:
        f.write("\n".join(out) + "\n")


def save_manifest(manifest):
    manifest["generated"] = datetime.now(timezone.utc).isoformat()
    manifest["file_count"] = len(manifest["files"])
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=0, sort_keys=True)

# --- main ---------------------------------------------------------------------

def main(argv):
    os.makedirs(INDEX_DIR, exist_ok=True)
    manifest = load_manifest()

    single = []
    it = iter(argv)
    for a in it:
        if a == "--file":
            single.append(next(it, ""))
        elif a.startswith("--file="):
            single.append(a.split("=", 1)[1])

    changed = 0
    if single:
        # Single-file update path (used by the PostToolUse hook).
        for f in single:
            if not f:
                continue
            rel = os.path.relpath(os.path.abspath(f), ROOT)
            if rel.startswith(".."):
                continue  # outside repo, ignore
            ext = os.path.splitext(rel)[1].lower()
            if ext not in INDEXED_EXT:
                continue  # not a code file we track
            if index_file(rel, manifest):
                changed += 1
    else:
        # Full reconcile against git.
        tracked = set(git_files())
        for rel in tracked:
            if index_file(rel, manifest):
                changed += 1
        # drop files no longer tracked
        for rel in list(manifest["files"]):
            if rel not in tracked:
                del manifest["files"][rel]
                changed += 1

    if changed or not os.path.exists(CODE_MAP):
        render_outputs(manifest)
        save_manifest(manifest)

    print(f"index: {len(manifest['files'])} files, {changed} changed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
