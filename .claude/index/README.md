# Claude Code Index

A self-maintaining, **token-cheap map of the whole codebase** so Claude can
locate code without re-reading source files every session.

## Files here

| File | Committed? | Purpose |
|------|:---------:|---------|
| `build_index.py` | ✅ | The generator. stdlib-only, deterministic (no LLM), ~0.25s full run. |
| `hook_postedit.sh` | ✅ | PostToolUse hook — re-indexes a single file after Claude edits it. |
| `hook_session.sh` | ✅ | SessionStart hook — reconciles the whole tree (catches PyCharm/git edits). |
| `manifest.json` | ❌ gitignored | Per-file `{sha, size, lang, symbols}`. Change-detection + cache. |
| `symbols.tsv` | ❌ gitignored | `symbol⇥kind⇥file⇥line` — **grep this to find code.** |
| `dependents.tsv` | ❌ gitignored | `file⇥dependent` — **grep this for blast radius** (who imports a file). |
| `imports.tsv` | ❌ gitignored | `file⇥imports` — forward direction (what a file depends on). |
| `CODE_MAP.md` | ❌ gitignored | Overview: most-depended-on files + files by area with their symbols. |
| `index.log` | ❌ gitignored | Hook run log. |

Generated artifacts are gitignored on purpose — they're rebuilt in ~0.25s at
session start, so committing them would only create noise and merge conflicts.

## How Claude should use it (read this first, before opening source)

1. **Find a symbol** (class / function / method / route / component):
   ```sh
   grep -i "MySymbol" .claude/index/symbols.tsv
   ```
   Each row gives you `file` and `line` — jump straight there.

2. **Blast radius before refactoring a file** (who breaks if I change it):
   ```sh
   grep '^path/to/file.py' .claude/index/dependents.tsv   # files that import it
   grep '^path/to/file.py' .claude/index/imports.tsv       # files it imports
   ```
   `CODE_MAP.md` lists the most-depended-on files up top (highest refactor risk).

3. **Understand a file/area before opening it:** skim the relevant section of
   `CODE_MAP.md` instead of reading the file cold.

4. **Only then read source** — and only the specific file+lines you need.

`kind` values: `class` `func` `method` `model` `serializer` `view` `route`
`test` (Python) · `export:component` `export:hook` `export:func` `component`
`hook` `func` `class` (JS/TS).

## Keeping it fresh

Automatic via the two hooks in `.claude/settings.json`:
- **Claude's edits** → `PostToolUse` re-indexes just that file (instant).
- **Your edits outside Claude** (PyCharm, `git pull`) → `SessionStart` reconciles
  the whole tree on the next session.

Manual rebuild anytime:
```sh
python3 .claude/index/build_index.py            # full reconcile
python3 .claude/index/build_index.py --file X   # one file
```

## Scope & limits

- Indexes `.py .js .jsx .ts .tsx` (symbols) plus `.sh .sql .html .css .scss
  .less .vue` (listed). Binaries (pdf/fonts/images) are skipped.
- Symbols come from regex, not a full parser — near-complete for navigation, but
  treat the map as a *pointer to* source, not a substitute for reading it when
  correctness matters.
