#!/usr/bin/env python3
"""Measured token report from Claude Code session transcripts (no estimates for API usage).

Usage:
  python3 .claude/scripts/token-report.py                 # every session of this project (summary table)
  python3 .claude/scripts/token-report.py --session ID    # one session, with breakdowns
  python3 .claude/scripts/token-report.py --since 2026-11-19 --json

API usage (input / cache write / cache read / output) is read from each assistant message's ``usage`` (deduplicated
by message id). Tool-output and injected-context sizes are BYTES of the transcript text (≈ bytes/4 tokens, marked
as estimates). Nothing is sent anywhere; read-only.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
from pathlib import Path

PROJECT_DIR = Path.home() / ".claude" / "projects" / ("-" + str(Path(__file__).resolve().parents[2]).strip("/").replace("/", "-"))


def _text_len(content) -> int:
    if isinstance(content, str):
        return len(content.encode())
    if isinstance(content, list):
        return sum(_text_len(c.get("text") if isinstance(c, dict) and "text" in c else c.get("content") if isinstance(c, dict) else c) for c in content)
    if isinstance(content, dict):
        return _text_len(content.get("text") or content.get("content") or "")
    return 0


def analyse(path: Path) -> dict:
    usage: dict[str, dict] = {}
    tool_names: dict[str, str] = {}
    tools = collections.Counter()
    tool_bytes = collections.Counter()
    attach_bytes = collections.Counter()
    models = collections.Counter()
    cost = None
    first = last = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = d.get("timestamp")
            if ts:
                first = first or ts
                last = ts
            kind = d.get("type")
            if kind == "assistant":
                msg = d.get("message") or {}
                if msg.get("id") and msg.get("usage"):
                    usage[msg["id"]] = msg["usage"]
                    models[msg.get("model") or "?"] += 0
                for c in msg.get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        tool_names[c.get("id")] = c.get("name")
                        tools[c.get("name")] += 1
                if msg.get("id"):
                    models[msg.get("model") or "?"] = models.get(msg.get("model") or "?", 0)
            elif kind == "user":
                for c in (d.get("message") or {}).get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "tool_result":
                        tool_bytes[tool_names.get(c.get("tool_use_id"), "?")] += _text_len(c.get("content"))
            elif kind == "attachment":
                att = d.get("attachment") or {}
                attach_bytes[att.get("type") or "?"] += len(json.dumps(att).encode())
            elif kind == "cost-state":
                cost = {"usd": d.get("totalCostUSD"), "models": list((d.get("modelUsage") or {}).keys())}
    tot = collections.Counter()
    for u in usage.values():
        tot["input"] += u.get("input_tokens") or 0
        tot["cache_write"] += u.get("cache_creation_input_tokens") or 0
        tot["cache_read"] += u.get("cache_read_input_tokens") or 0
        tot["output"] += u.get("output_tokens") or 0
    tot["requests"] = len(usage)
    return {"session": path.stem, "first": first, "last": last, "usage": dict(tot), "cost": cost,
            "tool_calls": dict(tools.most_common()), "tool_output_bytes": dict(tool_bytes.most_common()),
            "injected_bytes": dict(attach_bytes.most_common())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session")
    ap.add_argument("--since", help="ISO date; sessions whose first message is on/after it")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dir", default=str(PROJECT_DIR))
    args = ap.parse_args()
    files = sorted(Path(args.dir).glob("*.jsonl"), key=os.path.getmtime)
    if args.session:
        files = [f for f in files if f.stem.startswith(args.session)]
    rows = [analyse(f) for f in files]
    if args.since:
        rows = [r for r in rows if (r["first"] or "") >= args.since]
    if args.json:
        print(json.dumps(rows, indent=1))
        return
    for r in rows:
        u = r["usage"]
        total = u.get("input", 0) + u.get("cache_write", 0) + u.get("cache_read", 0) + u.get("output", 0)
        print(f"{r['session'][:8]}  {str(r['first'])[:16]}  req {u.get('requests', 0):>4}  in {u.get('input', 0):>8,}  "
              f"cache-write {u.get('cache_write', 0):>11,}  cache-read {u.get('cache_read', 0):>13,}  out {u.get('output', 0):>9,}  "
              f"total {total:>13,}  cost {((r['cost'] or {}).get('usd') or 0):>8.2f} USD")
        if args.session:
            print("  tool calls:", r["tool_calls"])
            print("  tool output bytes (≈/4 tokens):", r["tool_output_bytes"])
            print("  injected context bytes by attachment type (≈/4 tokens):", r["injected_bytes"])


if __name__ == "__main__":
    main()
