#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
run="cardinality-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "results/$run"
for mode in true false; do
  export DEMO_HIGH_CARDINALITY="$mode"
  docker compose --profile cardinality up -d --build --force-recreate cardinality-demo
  ready=0
  for attempt in {1..60}; do
    if curl --max-time 3 -fsS http://localhost:8010/health >/dev/null; then ready=1; break; fi
    sleep 2
  done
  [[ "$ready" == 1 ]] || { echo 'Demo did not become ready'; exit 1; }
  for number in {1..100}; do curl --max-time 5 -fsS -X POST http://localhost:8010/hit >/dev/null; done
  # The app container has Python even when the host does not.
  docker compose exec -T app python scripts/check-cardinality.py "$mode" | tee "results/$run/$mode.json"
done
echo "Evidence: results/$run. Low-cardinality demo remains running for screenshots."
echo 'Stop later: docker compose --profile cardinality stop cardinality-demo'
