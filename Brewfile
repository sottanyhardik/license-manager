# Local development CLI tools (Apple Silicon / Homebrew in /opt/homebrew).
# Install: brew bundle --file=Brewfile   (scripts/dev/bootstrap-macos.sh runs this)
# Python 3.14 comes from uv and Node 24 from ~/.local/node (see
# docs/development-environment/LOCAL-SETUP.md) — deliberately not from Homebrew,
# so there is exactly one interpreter of each on PATH.
brew "gh"
brew "ripgrep"
brew "fd"
brew "fzf"
brew "direnv"
brew "jq"
brew "libpq"      # psql/pg_dump/pg_isready + libpq for psycopg (keg-only; scripts add its bin to PATH)
brew "redis"      # for redis-cli only — the server runs in Docker; do NOT `brew services start redis`
