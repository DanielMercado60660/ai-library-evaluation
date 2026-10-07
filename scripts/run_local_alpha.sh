#!/usr/bin/env bash
# run_local_alpha.sh — Local preflight checker for AI Librarian eval platform.
# Validates prerequisites, port availability, and service health before development.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; FAILURES=$((FAILURES + 1)); }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }

FAILURES=0

echo "═══════════════════════════════════════════════"
echo " Pachyderm Archive — Local Preflight Check"
echo "═══════════════════════════════════════════════"
echo ""

# ── Prerequisites ──────────────────────────────────
echo "Prerequisites:"

if command -v uv &>/dev/null; then
  pass "uv $(uv --version 2>/dev/null | head -1)"
else
  fail "uv not found — install from https://docs.astral.sh/uv/"
fi

if command -v node &>/dev/null; then
  pass "node $(node --version)"
else
  fail "node not found — install Node.js 18+"
fi

if command -v npm &>/dev/null; then
  pass "npm $(npm --version)"
else
  fail "npm not found"
fi

if command -v python3 &>/dev/null; then
  pass "python3 $(python3 --version 2>&1 | awk '{print $2}')"
else
  fail "python3 not found"
fi

echo ""

# ── Port Availability ──────────────────────────────
echo "Port Availability:"

check_port() {
  local port=$1
  local label=$2
  if lsof -iTCP:"$port" -sTCP:LISTEN -P -n &>/dev/null; then
    pass "Port $port ($label) — in use (service likely running)"
  else
    warn "Port $port ($label) — free (service not running)"
  fi
}

check_port 8000 "agents"
check_port 8001 "catalog"
check_port 8002 "circulation"
check_port 8003 "ill"
check_port 8004 "registry"
check_port 8011 "catalog-mastodon"
check_port 8012 "catalog-mammoth"
check_port 8013 "catalog-ivory"
check_port 8014 "catalog-tusk"
check_port 4200 "frontend"

echo ""

# ── Service Health Checks ──────────────────────────
echo "Service Health:"

check_health() {
  local url=$1
  local label=$2
  local response
  if response=$(curl -sf --max-time 2 "$url" 2>/dev/null); then
    pass "$label — healthy"
  else
    warn "$label — not responding at $url"
  fi
}

check_health "http://127.0.0.1:8000/health" "Agents API (8000)"
check_health "http://127.0.0.1:8001/health" "Catalog (8001)"
check_health "http://127.0.0.1:8002/health" "Circulation (8002)"
check_health "http://127.0.0.1:8003/health" "ILL (8003)"
check_health "http://127.0.0.1:8004/health" "Registry (8004)"

echo ""
echo "Spoke Catalog Health (v1.7 federation):"

check_health "http://127.0.0.1:8011/health" "Mastodon Institute (8011)"
check_health "http://127.0.0.1:8012/health" "Mammoth Valley (8012)"
check_health "http://127.0.0.1:8013/health" "Ivory University (8013)"
check_health "http://127.0.0.1:8014/health" "Tusk Conservatory (8014)"

echo ""

# ── Frontend Build Check ──────────────────────────
echo "Frontend:"

FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"
if [ -d "$FRONTEND_DIR/node_modules" ]; then
  pass "node_modules present"
else
  warn "node_modules missing — run: cd frontend && npm install"
fi

if [ -d "$FRONTEND_DIR/dist" ]; then
  pass "dist/ build output present"
else
  warn "dist/ missing — run: cd frontend && ng build"
fi

echo ""

# ── Summary ────────────────────────────────────────
echo "═══════════════════════════════════════════════"
if [ "$FAILURES" -eq 0 ]; then
  echo -e " ${GREEN}Preflight complete — no blocking issues.${NC}"
else
  echo -e " ${RED}Preflight found $FAILURES blocking issue(s).${NC}"
fi
echo ""
echo " Startup guidance:"
echo "   Backend:  docker compose up --build -d"
echo "   Frontend: cd frontend && npm install && ng serve"
echo "   Tests:    uv run pytest -q"
echo "   E2E:      cd frontend && npm run e2e"
echo "═══════════════════════════════════════════════"

exit "$FAILURES"
