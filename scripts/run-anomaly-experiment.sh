#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
duration="${1:-2m}"
cooldown="${2:-310}"
run="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "results/$run"
app_port="${APP_PORT:-$(sed -n 's/^APP_PORT=//p' .env 2>/dev/null | tr -d '\r' || true)}"
app_url="http://localhost:${app_port:-8000}"
wait_ready() {
  for attempt in {1..60}; do
    if curl --max-time 3 -fsS "$app_url/ready" >/dev/null; then return; fi
    sleep 2
  done
  return 1
}
cleanup() {
  export FAULT_DELAY_ENABLED=false
  docker compose up -d --no-deps --force-recreate app
  wait_ready
}
trap cleanup EXIT
trap 'exit 130' INT TERM
printf 'phase,start,end,exit_code\n' > "results/$run/times.csv"
failed=0
for phase in baseline fault recovery; do
  export FAULT_DELAY_ENABLED=false
  if [[ "$phase" == fault ]]; then export FAULT_DELAY_ENABLED=true; fi
  docker compose up -d --no-deps --force-recreate app
  wait_ready
  if [[ "$phase" != baseline ]]; then sleep "$cooldown"; fi
  start="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "$phase starts $start"
  code=0
  docker compose --profile load run --rm -e "PHASE=$phase" -e "DURATION=$duration" \
    -e "SUMMARY_FILE=/results/$run/$phase.json" k6 run -o experimental-prometheus-rw /scripts/baseline.js || code=$?
  end="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '%s,%s,%s,%s\n' "$phase" "$start" "$end" "$code" >> "results/$run/times.csv"
  if (( code != 0 )); then failed=1; fi
done
echo "Evidence: results/$run"
exit "$failed"
