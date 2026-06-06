#!/usr/bin/env bash
# Convenience launcher for Weekend Planner (backend :8000 + frontend :3000).
#
# Usage:
#   ./dev.sh            # start both; Ctrl+C stops both (logs interleave)
#   ./dev.sh backend    # backend only  (clean logs — use a 2nd terminal for frontend)
#   ./dev.sh frontend   # frontend only
#   ./dev.sh health     # curl the backend /api/health and show provider status
#   ./dev.sh setup      # install deps + create .env files (first run / after a move)
#
# Overridable env:
#   HOST          default localhost (set HOST=0.0.0.0 to expose on your LAN / WSL / a remote box)
#   BACKEND_PORT  default 8000
#   FRONTEND_PORT default 3000
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${HOST:-localhost}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

preflight() {
  if [ ! -x "$ROOT/backend/.venv/bin/python" ]; then
    echo "✗ backend/.venv missing — run: ./dev.sh setup" >&2
    exit 1
  fi
  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    echo "✗ frontend/node_modules missing — run: ./dev.sh setup" >&2
    exit 1
  fi
}

backend() {
  cd "$ROOT/backend"
  exec .venv/bin/python -m uvicorn app.main:app --reload --host "$HOST" --port "$BACKEND_PORT"
}

frontend() {
  cd "$ROOT/frontend"
  exec pnpm dev -H "$HOST" -p "$FRONTEND_PORT"
}

health() {
  echo "→ http://localhost:${BACKEND_PORT}/api/health"
  curl -s "http://localhost:${BACKEND_PORT}/api/health" | python3 -m json.tool 2>/dev/null \
    || { echo "  (no response — is the backend running? ./dev.sh backend)"; exit 1; }
}

setup() {
  echo "→ backend deps (uv sync --extra dev)"
  ( cd "$ROOT/backend" && uv sync --extra dev )
  [ -f "$ROOT/backend/.env" ] || { cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"; echo "  created backend/.env — fill in API keys"; }
  echo "→ frontend deps (pnpm install)"
  ( cd "$ROOT/frontend" && pnpm install )
  [ -f "$ROOT/frontend/.env.local" ] || { cp "$ROOT/frontend/.env.example" "$ROOT/frontend/.env.local"; echo "  created frontend/.env.local — fill in AMAP JS key"; }
  echo "✓ setup done — now run ./dev.sh"
}

both() {
  preflight
  echo "▶ backend  http://localhost:${BACKEND_PORT}   (reload on)"
  echo "▶ frontend http://localhost:${FRONTEND_PORT}"
  echo "  Ctrl+C stops both."
  ( cd "$ROOT/backend" && .venv/bin/python -m uvicorn app.main:app --reload --host "$HOST" --port "$BACKEND_PORT" ) &
  local back=$!
  ( cd "$ROOT/frontend" && pnpm dev -H "$HOST" -p "$FRONTEND_PORT" ) &
  local front=$!
  trap 'kill "$back" "$front" 2>/dev/null || true' INT TERM EXIT
  wait
}

case "${1:-all}" in
  all)      both ;;
  backend)  preflight; backend ;;
  frontend) preflight; frontend ;;
  health)   health ;;
  setup)    setup ;;
  *) echo "usage: ./dev.sh [all|backend|frontend|health|setup]" >&2; exit 1 ;;
esac
