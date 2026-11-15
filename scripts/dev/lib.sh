# Shared helpers for scripts/dev-{start,stop,status,check}.sh. Source, don't run.
# Only ever manages processes it started itself (PID files in logs/dev/pids).
# shellcheck shell=bash

LM_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
LM_BACKEND="$LM_ROOT/backend"
LM_FRONTEND="$LM_ROOT/frontend"
LM_MDS="$LM_ROOT/master-data-service"
LM_VENV="$LM_BACKEND/.venv"
LM_MDS_VENV="$LM_MDS/.venv"
LM_LOG_DIR="$LM_ROOT/logs/dev"
LM_PID_DIR="$LM_LOG_DIR/pids"
LM_COMPOSE_ENV="$LM_ROOT/.env.local"

# User-space toolchain first (uv Python, ~/.local/node), then Homebrew, then Docker Desktop CLI.
export PATH="$HOME/.local/bin:$HOME/.local/node/bin:/opt/homebrew/bin:/opt/homebrew/opt/libpq/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
# psycopg (non-binary) locates libpq via `pg_config` on PATH → Homebrew libpq/bin above.
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES PYTHONUNBUFFERED=1

if [ -t 1 ]; then C_OK=$'\e[32m'; C_WARN=$'\e[33m'; C_ERR=$'\e[31m'; C_DIM=$'\e[2m'; C_0=$'\e[0m'; else C_OK=; C_WARN=; C_ERR=; C_DIM=; C_0=; fi
ok()   { printf '%s✔%s %s\n' "$C_OK" "$C_0" "$*"; }
warn() { printf '%s!%s %s\n' "$C_WARN" "$C_0" "$*"; }
err()  { printf '%s✘%s %s\n' "$C_ERR" "$C_0" "$*" >&2; }
info() { printf '%s·%s %s\n' "$C_DIM" "$C_0" "$*"; }

# Read KEY from a dotenv file without sourcing it (never echoes other values).
env_get() { [ -f "$1" ] && sed -n "s/^$2=//p" "$1" | tail -1; }

require_env_files() {
  local missing=0 f
  for f in "$LM_COMPOSE_ENV" "$LM_BACKEND/.env" "$LM_MDS/.env"; do
    [ -f "$f" ] || { err "missing ${f#"$LM_ROOT"/} — run: scripts/dev/init-local-env.sh"; missing=1; }
  done
  return $missing
}

assert_local_db() { # refuse anything that is not a local database
  local host; host=$(env_get "$LM_BACKEND/.env" DB_HOST); host=${DB_HOST:-${host:-localhost}}
  case "$host" in localhost|127.0.0.1|::1) return 0;; esac
  err "DB_HOST=$host is not local — refusing (see .claude/rules/safety.md)"; return 1
}

compose() { docker compose --project-directory "$LM_ROOT" -f "$LM_ROOT/docker-compose.yml" --env-file "$LM_COMPOSE_ENV" "$@"; }

docker_ready() {
  command -v docker >/dev/null 2>&1 || { err "docker CLI not found — install/launch Docker Desktop (docs/development-environment/LOCAL-SETUP.md)"; return 1; }
  docker info >/dev/null 2>&1 || { err "Docker daemon not running — open Docker Desktop and retry"; return 1; }
}

container_health() { docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$1" 2>/dev/null || echo absent; }

wait_healthy() { # container timeout_s
  local i
  for ((i = 0; i < $2; i++)); do
    [ "$(container_health "$1")" = healthy ] && return 0
    sleep 1
  done
  return 1
}

port_in_use() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# ── managed processes ────────────────────────────────────────────────
# name → expected command fragment (used to verify a PID before signalling it)
proc_marker() {
  case $1 in
    django) echo "manage.py runserver" ;;
    worker) echo "lmanagement worker" ;;
    beat)   echo "lmanagement beat" ;;
    vite)   echo "vite" ;;
  esac
}

# Prints the PID if the PID file points at a live process that is ours.
managed_pid() {
  local f="$LM_PID_DIR/$1.pid" pid
  [ -f "$f" ] || return 1
  pid=$(cat "$f")
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  ps -p "$pid" -o command= 2>/dev/null | grep -qF -- "$(proc_marker "$1")" || return 1
  echo "$pid"
}

# start_proc name workdir cmd...  — own process group (set -m) so stop can signal the group.
start_proc() {
  local name=$1 dir=$2; shift 2
  local pid
  if pid=$(managed_pid "$name"); then info "$name already running (pid $pid)"; return 0; fi
  mkdir -p "$LM_PID_DIR"
  set -m
  (cd "$dir" && exec nohup "$@" >>"$LM_LOG_DIR/$name.log" 2>&1 </dev/null) &
  pid=$!
  set +m
  echo "$pid" >"$LM_PID_DIR/$name.pid"
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then ok "$name started (pid $pid, log logs/dev/$name.log)"
  else err "$name exited immediately — see logs/dev/$name.log"; tail -20 "$LM_LOG_DIR/$name.log" >&2; return 1; fi
}

stop_proc() {
  local name=$1 pid i
  if ! pid=$(managed_pid "$name"); then rm -f "$LM_PID_DIR/$name.pid"; info "$name not running"; return 0; fi
  # Signal the process group only if this PID leads it (it does when we started it).
  if [ "$(ps -o pgid= -p "$pid" | tr -d ' ')" = "$pid" ]; then kill -TERM -- "-$pid" 2>/dev/null; else kill -TERM "$pid" 2>/dev/null; fi
  for ((i = 0; i < 15; i++)); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
  if kill -0 "$pid" 2>/dev/null; then
    warn "$name did not stop after 15s — sending SIGKILL to its group"
    kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null
  fi
  rm -f "$LM_PID_DIR/$name.pid"
  ok "$name stopped"
}
