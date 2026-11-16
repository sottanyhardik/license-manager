# JetBrains Central CLI — integration notes (verified 2026-11-16)

Everything below was observed on this machine with `central 2.5.0`. Only commands listed by
`central --help` were used. No token contents were read or printed.

## Installed state

| Item | Observed |
|---|---|
| Binary | `~/.local/bin/central` — **2.5.0** (commit a86738de, built 2026-11-05); the prompt's "0.1.20" is outdated |
| Update | `central status` → "up to date", track `stable`. (`central update` was **not** run: it prompts and installs) |
| Auth | Logged in, personal JetBrains Account (normal browser OAuth). No Enterprise server configured; `--enterprise` not used |
| AI access sources | 2 personal licences; the current one is valid through 2029-07-23 (`central access`) |
| Proxy | running on `127.0.0.1:19516` (`central status`); config: log level info, analytics on, "Approve all MCP policies: on" |
| Agents | "Claude Agent: installed · configured"; Junie/Codex/Gemini CLI/Pi/Copilot not installed (`central agents`) |
| Plugins | none (`central plugins`) |
| Claude Code plugin | `jetbrains-central@jetbrains-central` (user scope) is enabled in `~/.claude/settings.json` |

## Quota (`central limit`, at setup)

| | Used | Total | Remaining |
|---|---|---|---|
| Monthly quota | 10.00 | 10.00 | **0.00** |
| Top-up credits | 7.86 | 356.82 | 348.97 |
| Combined | 17.86 | 366.82 | 348.97 (4.9 % used) |

Quota period Nov 4 – Dec 4, 2026. The included monthly quota is **exhausted**; requests currently draw on
**top-up credits**. These are JetBrains AI credits, **not** Anthropic API credits. `central limit` doesn't
show per-model restrictions. The models allowed through the gateway are the ones listed in
`~/.claude/settings.json` → `availableModels` (`enforceAvailableModels: true`). Multi-agent waves use credits
quickly, so check `central limit` before and after a large orchestration run.

## How Claude Code is wired (actual architecture)

```
claude (Claude Code 2.1.325)
  ├─ ANTHROPIC_BASE_URL = http://127.0.0.1:19516/…   (user settings env, written by `central add`)
  ├─ apiKeyHelper      = central …                    (short-lived credential from Central; not a stored key)
  └─► Central local proxy ──► JetBrains AI ("JetBrains Air") ──► Anthropic models
PyCharm AI Assistant ─► separate IDE service/login (not used by Claude Code)
PyCharm MCP server   ─► http://127.0.0.1:<port>/stream, registered globally as `pycharm` (IDE tools only, no model access)
```

Facts and non-assumptions:
- This setup session and the headless checks (`claude -p --model sonnet|opus|haiku`) all ran **through
  Central**. Aliases resolved to claude-sonnet-5-5 / claude-opus-5-5 / claude-haiku-5-5.
- **No separate direct Anthropic authentication was found** in Claude settings. As configured, Claude Code is
  **not** independent of Central: if the proxy is down, model calls fail (seen in `central log`: two `502`s
  from `local-proxy` at 08:51 during a proxy restart, and three `477` upstream errors at 08:03).
- Central login doesn't log in PyCharm AI Assistant, and the reverse isn't true either. A JetBrains AI
  subscription is not unrestricted Anthropic API access, and Central quota isn't Anthropic credit.
- The orchestration layer (agents, skills, hooks, queue) does not depend on Central. It works the same with
  any Claude Code auth.
- Central must never be used to get around Claude Code permissions or the project hooks. Both apply
  regardless of the model provider.

## Routine checks (read-only, allowlisted)

```
central status        # auth, proxy, version, traffic
central limit         # credits
central access        # licence sources
central agents        # agent registration
central log --status errors --limit 10 --time day
claude mcp list       # pycharm MCP health
```

## Recovery

| Symptom | Action (owner runs these; agents are blocked from credential/config removal) |
|---|---|
| `502` / connection refused on 127.0.0.1:19516 | `central status`, then `central proxy restart` |
| auth expired / `401` | `central login` (browser OAuth, personal account), then `central status` |
| agent config drifted | `central repair` (refreshes credentials and agents, restarts proxy) |
| quota/credits exhausted (`477`-type errors) | `central limit`; wait for the period reset or top up in the JetBrains account |
| need Claude Code **without** Central | owner decision: `central remove` (removes Central config from the agent; reversible with `central add`), then authenticate Claude Code directly (`claude` → `/login`). Back up `~/.claude/settings.json` first |
| switch licence | `central access` (lists sources; switching is interactive) |

Blocked for agents (deny rules and hook): `central logout`, `central uninstall`, `central remove`,
`central login export/import/--secret/--clientId`, any access to `tokens.enc`. Not touched during setup:
`tokens.enc`, credentials, JetBrains account authorisation, user-level `~/.claude/settings.json`.
