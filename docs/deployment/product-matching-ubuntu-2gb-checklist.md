# Product matching — Ubuntu 24.04 deployment checklist (2 GB RAM / 2 vCPU / 10 GB free)

Scope: deploy the local MiniLM product-matching engine (migrations `license.0058`, `license.0059`, Celery queue
`matching`) without affecting normal ERP use. **Prepared only — nothing here was run on the server.** Every step that
touches the server needs the owner's explicit go-ahead; run them yourself or authorise them one by one.

Fill the `Result` column as you go; stop at the first ✗ and use **Rollback**.

## 0. Before you start

| # | Check | Command | Expected | Result |
|---|---|---|---|---|
| 0.1 | Code is the reviewed build | `git -C <app> log --oneline -5` | includes the product-matching commit on `feature/v5` | |
| 0.2 | Database backup taken | your standard `pg_dump` procedure | backup file + size recorded | |
| 0.3 | Maintenance window agreed | — | owner sign-off | |

## 1. Inspect the server (read-only)

| # | Check | Command | Expected | Result |
|---|---|---|---|---|
| 1.1 | CPU arch / flags | `uname -m; lscpu \| grep -E 'Model name\|Flags' \| head -2` | `x86_64` with `avx2` (or `aarch64`) | |
| 1.2 | vCPUs | `nproc` | 2 | |
| 1.3 | RAM / swap | `free -m` | note `available` and swap; **if no swap, add 1–2 GB swap before continuing (owner decision)** | |
| 1.4 | Disk | `df -h <app> /tmp` | ≥ 1 GB free after install (model 23 MB, wheels ~60 MB) | |
| 1.5 | Running services | `systemctl --type=service --state=running \| grep -Ei 'gunicorn\|uvicorn\|celery\|postgres\|redis\|nginx'` | ERP services listed; note existing Celery units | |
| 1.6 | Baseline memory per process | `ps -eo pid,rss,comm --sort=-rss \| head -15` | record gunicorn / celery / postgres RSS | |
| 1.7 | Baseline ERP latency | `curl -s -o /dev/null -w '%{time_total}\n' https://<host>/api/health/` ×5 (or a light authenticated page) | record median | |
| 1.8 | Python | `<venv>/bin/python --version` | 3.14.x (same as CI) | |

## 2. Install (no PyTorch, no Transformers)

| # | Step | Command | Expected | Result |
|---|---|---|---|---|
| 2.1 | Dependencies | `<venv>/bin/pip install -r backend/requirements.txt` | installs `onnxruntime==1.32.0`, `tokenizers==0.23.3`; **`pip list \| grep -Ei 'torch\|transformers'` prints nothing** | |
| 2.2 | Migrations (additive tables only) | `python manage.py migrate license 0059` | `0058_product_match_decision`, `0059_product_matching_jobs_embeddings` OK | |
| 2.3 | No other drift | `python manage.py makemigrations --check --dry-run` | `No changes detected` | |

## 3. Model download + verification

| # | Step | Command | Expected | Result |
|---|---|---|---|---|
| 3.1 | Variant detection | `python manage.py product_matching_model --status` | `variant=avx2` (or `avx512`/`avx512_vnni`/`arm64`) matching 1.1 | |
| 3.2 | Download pinned files | `python manage.py product_matching_model --download` | revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`; `onnx.verified=True`, `tokenizer.verified=True` | |
| 3.3 | Independent checksum | `sha256sum backend/var/models/all-MiniLM-L6-v2/1110a243*/model_*.onnx` | AVX2 `b941bf19f1f1283680f449fa6a7336bb5600bdcd5f84d10ddc5cd72218a0fd21`; ARM64/AVX512 `4278337fd0ff3c68bfb6291042cad8ab363e1d9fbc43dcb499fe91c871902474` | |
| 3.4 | File size | `ls -l backend/var/models/all-MiniLM-L6-v2/*/` | ONNX ≈ 23 MB; `tokenizer.json` 466,247 bytes | |
| 3.5 | Permissions | `chown -R <app-user>: backend/var/models` | readable by the Celery user only | |

## 4. CPU / RAM benchmark (before enabling the worker)

| # | Step | Command | Expected | Result |
|---|---|---|---|---|
| 4.1 | Benchmark | `python manage.py product_matching_model --benchmark` | record `load+first`, `per_record` at batch 4 and 8, `peak_rss`, `available` | |
| 4.2 | Decide batch size | — | keep **batch 4**; allow 8 only if peak RSS stays < 600 MB **and** `available` stays > 600 MB during 4.1 | |
| 4.3 | Sanity line | (printed by 4.1) | `PP~polypropylene` > `PP~paper-board`; `foil~alu-foil` ≥ 0.7 | |

Reference (dev Mac arm64, **not** the server): load 0.16 s, 4.5 ms/record @4, 8.1 ms/record @8, Django process peak 285 MB.

## 5. One-worker configuration

Create a **separate** systemd unit so the ERP Celery workers are untouched (example — adapt paths/user):

```ini
# /etc/systemd/system/lm-celery-matching.service
[Unit]
Description=License Manager — product matching worker (1 process)
After=network.target redis-server.service postgresql.service

[Service]
User=<app-user>
WorkingDirectory=<app>/backend
Environment=PRODUCT_MATCH_MIN_AVAILABLE_MB=350
Environment=OMP_NUM_THREADS=1
ExecStart=<venv>/bin/celery -A lmanagement worker -Q matching -c 1 --prefetch-multiplier=1 \
          --max-tasks-per-child=1 --max-memory-per-child=700000 -n matching@%%h
Nice=10
CPUQuota=100%
MemoryHigh=800M
MemoryMax=900M
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

| # | Step | Command | Expected | Result |
|---|---|---|---|---|
| 5.1 | ERP workers do NOT consume `matching` | inspect existing unit `-Q` options | `matching` not in their queue list | |
| 5.2 | Start | `systemctl daemon-reload && systemctl start lm-celery-matching` | `active (running)` | |
| 5.3 | Health | UI Item Pivot → Product Matching shows "Matching worker online", or `GET /api/item-pivot/matching/health/` | `model.ok=true`, `worker.ok=true` | |

Limits in force: 1 process, 1 inference thread (`intra_op_num_threads=1`), batch 4 (max 8), one task at a time
(`-c 1 --prefetch-multiplier=1`), `nice` 10, systemd `MemoryHigh/Max`, automatic pause below 350 MB `MemAvailable`.

## 6. First run + memory monitoring

| # | Step | Command | Expected | Result |
|---|---|---|---|---|
| 6.1 | Start a small job | UI: Product Matching → *Run semantic classification* with one norm selected | job QUEUED → RUNNING → DONE | |
| 6.2 | Watch memory | `watch -n 2 'free -m; ps -o pid,rss,cmd -C celery'` | worker RSS < 700 MB; `available` > 350 MB; no swap storm (`vmstat 2` `si/so` ≈ 0) | |
| 6.3 | Job metrics | UI job line / `GET /api/item-pivot/matching/jobs/` | `seconds`, `peak_rss_mb`, `embedded_new`, `min_available_mb` recorded | |
| 6.4 | Pause / resume | UI Pause, then Resume | status PAUSED then DONE; no duplicate embeddings (`embedded_new`=0 on a re-run) | |
| 6.5 | Memory-pressure pause | (optional) set `PRODUCT_MATCH_MIN_AVAILABLE_MB` above current available, restart worker, run job | job PAUSED with "Memory pressure" reason | |

## 7. ERP stays responsive

| # | Check | Command | Expected | Result |
|---|---|---|---|---|
| 7.1 | Latency during a job | repeat 1.7 while 6.1 runs | median within ~20 % of baseline | |
| 7.2 | Normal pages | open Licences, Allotments, BOE, Item Pivot (Intelligence + Classic) | load normally | |
| 7.3 | ERP Celery queue | `celery -A lmanagement inspect active` | ERP tasks keep completing; matching task only on `matching@` | |
| 7.4 | No financial change | `SELECT count(*) FROM license_licenseitemplan;` and BOE/allotment row counts before/after a job | unchanged (approvals only change master-item links) | |

## 8. Accuracy record (after reviewers have decided some suggestions)

`python manage.py evaluate_product_matching --sample 300 --semantic` and
`python manage.py evaluate_product_matching --truth decisions` — store the output with the deployment record. Do not
quote accuracy figures beyond these measurements.

## Rollback

1. Stop the matching worker: `systemctl stop lm-celery-matching && systemctl disable lm-celery-matching`
   (ERP is unaffected — the web app never runs inference; the Product Matching tab then shows "No matching worker").
2. If the feature must be removed entirely: deploy the previous build, then
   `python manage.py migrate license 0057_licensebalance_balance_cif_signed` — drops only the four product-matching
   tables. **This also deletes the decision audit history**; export it first
   (`python manage.py dumpdata license.ProductMatchDecision > product_match_decisions.json`).
3. Approved matches already linked import items to master items; reverting those links is a data change — use the
   `previous_links` recorded on each `ProductMatchDecision` and agree it with the owner before applying.
4. Model files: `rm -rf backend/var/models/all-MiniLM-L6-v2` (re-downloadable, checksum-verified).
5. Dependencies may stay installed; or `pip uninstall onnxruntime tokenizers` after the previous build is live.
