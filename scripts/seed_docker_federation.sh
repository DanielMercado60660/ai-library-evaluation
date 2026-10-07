#!/usr/bin/env bash
# seed_docker_federation.sh — Seed spoke catalog databases and registry in Docker.
# Run after `docker compose up --build -d` to provision federated catalogs.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }

echo "═══════════════════════════════════════════════"
echo " Pachyderm Archive — Docker Federation Seeder"
echo "═══════════════════════════════════════════════"
echo ""

# ── Wait for spoke catalogs to be healthy ─────────────────
echo "Waiting for spoke catalog services..."

SPOKES=("catalog-mastodon:8000" "catalog-mammoth:8000" "catalog-ivory:8000" "catalog-tusk:8000" "catalog:8000")
PORTS=(8011 8012 8013 8014 8001)
LABELS=("Mastodon Institute" "Mammoth Valley" "Ivory University" "Tusk Conservatory" "Hanno Memorial")

for i in "${!PORTS[@]}"; do
    port=${PORTS[$i]}
    label=${LABELS[$i]}
    for attempt in $(seq 1 30); do
        if curl -sf --max-time 2 "http://127.0.0.1:${port}/health" > /dev/null 2>&1; then
            pass "${label} (port ${port}) — healthy"
            break
        fi
        if [ "$attempt" -eq 30 ]; then
            fail "${label} (port ${port}) — not responding after 30 attempts"
            exit 1
        fi
        sleep 1
    done
done

echo ""

# ── Seed spoke catalog databases ─────────────────────────
echo "Seeding spoke catalog databases..."

declare -A CODE_MAP=(
    ["catalog-mastodon"]="mastodon-institute"
    ["catalog-mammoth"]="mammoth-valley"
    ["catalog-ivory"]="ivory-university"
    ["catalog-tusk"]="tusk-conservatory"
)

for container in catalog-mastodon catalog-mammoth catalog-ivory catalog-tusk; do
    code=${CODE_MAP[$container]}
    echo "  Seeding ${code}..."
    docker compose exec -T "${container}" python -c "
import sys
sys.path.insert(0, '/app/services/catalog/src')
sys.path.insert(0, '/app/shared/src')
sys.path.insert(0, '/app/scripts')
from seed_spoke_catalog import seed_library
result = seed_library('${code}', 'sqlite:///./db/catalog.db')
print(f\"  Books: {result['books_seeded']}, Instances: {result['instances_generated']}\")
" && pass "${code} seeded" || fail "${code} seed failed"
done

echo ""

# ── Seed registry with spoke catalog URLs ─────────────────
echo "Seeding registry with spoke catalog URLs..."
python scripts/seed_registry_federation.py --docker --registry-url http://127.0.0.1:8004

echo ""

# ── Smoke test ────────────────────────────────────────────
echo "Smoke test: query mastodon catalog for book-501..."
RESULT=$(curl -sf "http://127.0.0.1:8011/books?isbn=978-0-GHLS-0501" 2>/dev/null || echo "FAIL")
if echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['total']>=1" 2>/dev/null; then
    pass "Mastodon catalog returns book-501"
else
    fail "Mastodon catalog smoke test failed"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo -e " ${GREEN}Federation seeding complete.${NC}"
echo "═══════════════════════════════════════════════"
