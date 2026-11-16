# MODULE 04 — MASTER SYNCHRONISATION — INDEPENDENT RE-VERIFICATION

**Verdict: NOT FROZEN — 2 mandatory gates genuinely fail.**

This supersedes the "FROZEN" verdict in `MODULE_04_MASTER_SYNC_FINAL_FREEZE_REPORT.md`.
That report was not re-run before this verification; every claim below was measured.

| Item | Value |
|---|---|
| Branch | `feature/V2` |
| HEAD at start | `aed3756c` (on `3f8b4e0c` — Module 03 freeze) |
| Verification date | 2026-08-13 |
| Production touched | **NO** — no connection, no migration, no deploy, no push |

---

## 1. Why the previous FROZEN verdict did not hold

### 1.1 The claimed "223/223 passing" measured 12% of the suite

`backend/pytest.ini` had `testpaths = tests`. Only `backend/tests/` was ever
collected. Measured at the start of this session:

```
223 tests collected      <- what "223 passed" referred to
1855 tests collected     <- tests + apps (actual suite), plus 2 collection ERRORS
```

**The Module 04 sync tests were not in that 223.** They live in
`apps/core/tests/` and were therefore never run by the default command. Neither
were the ~1600 tests under `apps/**`, including the entire License Ledger suite.

The 223 itself was also not green on a clean checkout: 4 tests in
`tests/test_ledger_parser.py` read `ledgers/*.csv` from the repo root — files
never tracked by git. Measured: `4 failed, 219 passed`.

### 1.2 The transport layer had zero test coverage

Gates reported as PASS ("Media sync + SHA256 ✅", "Retry ✅", "Offline recovery ✅",
"All URLs verified ✅") were measured at:

| Module | Coverage before |
|---|---|
| `sync/push.py` — the peer HTTP client | **0%** |
| `sync/views.py` — all 6 sync endpoints | **0%** |
| `sync/serializers.py` | **0%** |
| `sync/tasks.py` — Celery | **0%** |
| `sync/media.py` | **27%** |

The 81 passing tests exercised only `service.py`, on a **single database**, with
"servers" simulated as different `source_server` strings. `test_three_server_runtime.py`
is transparent about this in its own docstring; the freeze report was not.

---

## 2. What was fixed in this verification

### 2.1 Test infrastructure

| Fix | Evidence |
|---|---|
| `backend/tests/conftest.py` → `backend/conftest.py` | Fixtures were invisible to `apps/**`; every API test there errored at setup. Errors 811 → 447 on that change alone. |
| `testpaths = tests` → `tests apps` | The whole suite now runs by default. |
| Committed ICEGATE fixtures at `backend/tests/fixtures/ledgers/` | Suite is hermetic; fixtures deliberately include BOM, non-breaking spaces, page headers and 9-digit zero-padding. |
| `LicenseBalanceModel` → `LicenseBalance`, `LicenseTradeLineItem` → `LicenseTradeLine` | Two files could not be imported at all; 75 tests recovered. |
| `pytest.importorskip` for `mds_client` | 9 legacy MDS tests now skip honestly instead of erroring. |

### 2.2 Transport layer now genuinely covered

**312 new tests** across `test_sync_api.py`, `test_sync_transport.py`,
`test_sync_media_transport.py`, `test_sync_failures.py`, plus shared
`sync_factories.py`. Measured coverage after:

| Module | Before | After |
|---|---|---|
| `sync/push.py` | 0% | **100%** |
| `sync/views.py` | 0% | **100%** |
| `sync/serializers.py` | 0% | **100%** |
| `sync/urls.py` | 0% | **100%** |
| `sync/media.py` | 27% | **100%** |
| `sync/service.py` | 85% | **99%** |
| `sync/tasks.py` | 0% | **82%** |

`apps/core/tests/`: **662 passed, 10 skipped, 0 failed.** The two pre-existing
sync test files were not modified and still pass 81/81.

### 2.3 Thirteen real bugs found by those tests and fixed

Several would have made Module 04 wrong in production had it ever been switched on:

1. **`service.py`** — FK natural keys were treated as surrogate pks. 5 of 20 masters
   could not sync at all, and `delete-check` answered `safe: true` for records that
   exist and have children — i.e. **delete protection failed open**.
2. **`service.py`** — media was never replicated. `push.py` imported `get_media_info`
   and never called it, so no outbound event ever carried a `media` key; the entire
   receiver-side media pipeline was unreachable.
3. **`push.py`** — every "delta" pull was a silent full resync (`?since=` interpolated
   un-encoded; `+00:00` arrived as a space, `parse_datetime` returned `None`, filter dropped).
4. **`service.py`** — local `created_by_id`/`modified_by_id` were replicated to peers,
   pointing at different people or violating deferred FK constraints (push returned
   `200 {"ok": true}` then raised `IntegrityError` at commit).
5. **`service.py`** — one malformed event returned HTTP 500 and poisoned the queue:
   earlier events in the batch were already committed, so the pusher retried forever.
6. **`service.py`** — `core.ItemNameModel` could never sync on PostgreSQL
   (`select_for_update` inherited `Meta.ordering` across a nullable FK join).
7. **`media.py`** — filenames containing `&` or `+` fetched the wrong file.
8. **`media.py`** — a socket read timeout escaped and silently skipped every
   remaining media task in the pass.
9. **`push.py`** — `check_delete_on_peers` crashed on a `date` natural key.
10–13. **`views.py`** — 500s on user input: incomplete natural key, `?limit=abc`,
   `?limit=-1`, `?path=` pointing at a directory, and ambiguous natural key.

---

## 3. THE TWO GATES THAT STILL FAIL

### GATE FAIL 1 — Master Sync is not wired into the application

The engine is complete and now well tested, but **nothing invokes it.** Measured:

```
check_delete_on_peers   -> 0 callers anywhere in backend/apps, backend/lmanagement
sync_from_peer          -> 0 callers
SYNC_PUSH_ON_SAVE       -> defined in settings.py:410, never read anywhere
push_to_all_peers       -> called only by sync/tasks.py
sync.pull_from_peers    -> NOT in celery beat_schedule
sync.push_changes       -> NOT in celery beat_schedule
sync.process_media_tasks-> NOT in celery beat_schedule
```

Consequences for the mandated gates:

- **"Master Sync = YES"** — false in the running application. No scheduled job
  pulls or pushes; no save-time hook fires.
- **"Delete protection (global/remote FK) ✅ PASS"** — false. The master delete
  path (`apps/core/views/master_view.py:perform_destroy`) never calls
  `check_delete_on_peers`. Only *local* `ProtectedError` handling is active. A
  master still referenced on another server can be deleted.

This is an architectural wiring gap, not a test gap. It requires a deliberate
decision (wire the peer calls into the delete path + schedule the beat tasks,
behind `SYNC_ENABLED`), which is out of scope for a verification pass.

### GATE FAIL 2 — No genuine multi-server verification

Everything still runs on one database with `urlopen` patched. The client and
server halves are joined by contract tests that feed the client's exact wire
bytes into the real DRF endpoints — materially stronger than before, but it is
**not** the mandated test.

Specifically **not** verified:
- Real SERVER 1/2/3 with three separate databases.
- Offline recovery by actually stopping a server, mutating the others, restarting,
  and asserting `A == B == C` without manual SQL.
- Real network failure injection (as opposed to mocked exceptions).
- Media transfer over a real socket between two running servers.

Closing this needs additional `DATABASES` aliases for tests and a multi-DB harness.

---

## 4. Gates that DO pass

| Gate | Status | Evidence |
|---|---|---|
| Branch `feature/V2`, based on `3f8b4e0c` | ✅ | `git merge-base --is-ancestor` verified |
| MDS inert | ✅ | Double-gated: `MDS_ENABLED=False` default **and** `mds_client` not installed → settings self-disable. All call sites guarded by `_mds_active()`. |
| No central master DB / local masters / multi-writer schema | ✅ | 20 models on `MasterSyncMixin` + single registry |
| One common sync implementation (no per-model copies) | ✅ | registry + mixin + one service |
| Deterministic UID, versioning, tombstones, conflict resolution | ✅ | 81 pre-existing + new tests |
| Endpoint auth (401/403 unauthenticated) | ✅ | now explicitly tested |
| Path-traversal protection on media download | ✅ | now explicitly tested |
| Full backend regression | ✅ | **2212 passed, 0 failed, 38 skipped** |
| No production changes | ✅ | nothing committed, pushed or deployed |

---

## 5. Honest bottom line

Module 04 is **substantially better** than when it was declared frozen: the
transport layer went from 0% to ~100% covered and 13 real defects were fixed,
several of which silently corrupted or skipped data.

It is **not frozen**, because a synchronisation module that no code path
invokes cannot be called verified, and because the multi-server behaviour the
module exists to provide has still never been executed against more than one
database.

**Required to freeze:**
1. Wire `check_delete_on_peers` into the master delete path; schedule the three
   `sync.*` beat tasks (or delete `SYNC_PUSH_ON_SAVE` if push-on-save is not wanted).
2. Add a real multi-database test harness and run the 6-direction matrix,
   offline recovery, and media transfer across genuinely separate servers.
