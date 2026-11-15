#!/bin/sh
# Environment doctor — read-only health check of the Claude + JetBrains + toolchain setup.
ROOT=$(cd "$(dirname "$0")/../.." && pwd); cd "$ROOT" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/opt/homebrew/opt/node@24/bin:/opt/homebrew/opt/postgresql@18/bin:$PATH"
ok=0; bad=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "  OK    $1"; ok=$((ok+1)); else echo "  MISS  $1  → $3"; bad=$((bad+1)); fi; }
echo "Toolchain"
chk "claude CLI on PATH"        "command -v claude"                                  "add ~/.local/bin to PATH (bootstrap step 4)"
chk "node >= 24"                "node -e 'process.exit(+process.versions.node.split(\".\")[0]>=24?0:1)'" "bootstrap step 3"
chk "npm"                       "command -v npm"                                     "bootstrap step 3"
chk "gh (GitHub CLI)"           "command -v gh"                                      "bootstrap step 3"
chk "uv"                        "command -v uv"                                      "bootstrap step 3"
chk "Python 3.14 venv"          "$ROOT/.venv-3.14/bin/python -c 'import sys; assert sys.version_info>=(3,14)'" "bootstrap step 6"
chk "Django in 3.14 venv"       "$ROOT/.venv-3.14/bin/python -c 'import django; assert django.VERSION[0]>=6'" "bootstrap step 6"
chk "frontend node_modules"     "test -d frontend/node_modules"                      "cd frontend && npm ci"
chk "Postgres on localhost:5432" "python3 -c \"import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(s.connect_ex(('localhost',5432)))\"" "brew services start postgresql@18"
chk "Redis on localhost:6379"   "python3 -c \"import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(s.connect_ex(('localhost',6379)))\"" "brew services start redis"
echo "JetBrains"
chk "PyCharm installed"         "test -d /Applications/PyCharm.app"                  "install PyCharm"
chk "Claude Code JetBrains plugin" "ls \"$HOME/Library/Application Support/JetBrains/\"PyCharm*/plugins | grep -qi claude" "Settings → Plugins → Marketplace → Claude Code"
echo "Claude project config"
chk "settings.json valid JSON"  "python3 -m json.tool .claude/settings.json"         "fix JSON syntax"
chk "guard hook blocks force-push" "! echo '{\"tool_input\":{\"command\":\"git push --force\"}}' | python3 .claude/hooks/guard_bash.py" "check .claude/hooks/guard_bash.py"
chk "guard hook allows git status" "echo '{\"tool_input\":{\"command\":\"git status\"}}' | python3 .claude/hooks/guard_bash.py" "check .claude/hooks/guard_bash.py"
chk "code index builds"         "python3 .claude/index/build_index.py"              "see .claude/index/index.log"
chk "agents have frontmatter"   "for f in .claude/agents/*.md; do [ \$(basename \$f) = README.md ] || head -1 \$f | grep -q '^---\$' || exit 1; done" "fix agent file header"
echo "Result: $ok ok, $bad missing"
[ $bad -eq 0 ]
