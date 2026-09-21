# Archived native verification — 21 September 2026

This is the historical pre-Docker record. Its pending items describe that earlier run; the subsequent Docker results and current status are in [VERIFICATION.md](VERIFICATION.md).

The repository was empty at inspection. Host: Windows, PowerShell 5.1, 16 logical CPUs. The available Python environment used **Python 3.13**, while the delivered Dockerfile pins **Python 3.12.10**. Docker Desktop/daemon was not installed, so the complete Docker deployment was **not** started. Portable tools were downloaded to ignored `.tools/`; they do not need to be committed or installed for normal Compose usage. Test/benchmark database files and raw runtime logs remain ignored.

## Checks actually executed

| Check | Actual result |
|---|---|
| `python -m ruff check app tests scripts experiments` | Passed |
| `python -m ruff format --check app tests scripts experiments` | Passed, 30 Python files formatted |
| `python -m compileall -q app experiments scripts` | Passed |
| `python -m pip check` | No broken requirements; all direct/transitive dependencies pinned |
| Unit tests without PostgreSQL | 20 passed, 6 explicitly skipped initially |
| Full pytest suite against PostgreSQL 16.9 | **26 passed in 8.32s**, no skipped tests |
| Real DB invariants | 20 simultaneous same-slot requests: exactly one 201, nineteen409; DB row count one; direct overlapping SQL rejected; parallel cancellation counted once; adjacency/cancel/rebook passed |
| Standalone Docker Compose 2.36.2 `config --quiet` | Passed for default configuration and all optional profiles. Does not prove container build/start. |
| Prometheus 3.4.0 `promtool check config` | Passed |
| Filebeat8.19.0 `test config` | **Config OK** from the actual portable Filebeat binary, including configured timestamp parser self-test. This is not an Elasticsearch output test. |
| All dashboard expressions via `promtool check rules` | **46 expressions passed** |
| Dashboard expressions against a live native Prometheus | All 46 accepted with success responses; [saved results](evidence/native/dashboard-query-validation.json). Node metrics return no data on this native run; syntax success is not collector verification. |
| PowerShell scripts | Parsed with PowerShell's actual AST parser, no syntax errors |
| Bash scripts | `bash -n` passed under Git Bash |
| k6 1.0.0 profiles | All five passed `k6 inspect` |
| Native API startup / DB / `/health`, `/ready`, `/metrics` | Exercised with a real PostgreSQL 16.9 server and Uvicorn |
| Native real DB outage/recovery | Stopping PostgreSQL produced503 from readiness/rooms while health/metrics stayed200; restarting DB restored200 without restarting the app. [Actual observations](evidence/native/database-outage.json). |
| Native baseline/fault/recovery | Three 10-VU, 30-second profiles completed, exit code0, all thresholds passed |
| k6 remote-write series and units | Actual TSDB samples contain `k6_vus`, `k6_unexpected_responses_rate` and `k6_http_req_duration_p95/p99` in seconds. [Recorded metric names](evidence/native/k6-prometheus-metric-names.json). These become stale at run end as configured. |
| Native k6 same-slot batch | Exactly one winner and nineteen conflicts; thresholds passed |
| Live native Prometheus cardinality | **100 → 1** current counter-value series after removing the label and restarting demo; each mode accepted100, request101 returned429 |

The initial sandbox denied Python/pytest temporary directories and Git Bash signal pipes. Those commands were rerun with normal local permissions; application behavior was not weakened to make tests pass. PostgreSQL ran as a temporary loopback-bound process on port55432, **not a Windows service**, with an isolated `campus_test` database for the destructive test fixture and a separate `campus_native` database for benchmarks.

## Actual modest native load results

Environment: Python3.13/Uvicorn one worker, PostgreSQL16.9, k6 1.0.0, native Prometheus3.4.0. All on the same Windows host, no Docker memory/CPU quotas. Load generator and services compete for host resources. **No ELK or Node Exporter** was running; CPU/memory consumption and a saturation limit were not measured. Default pool10+5, requests perform the committed business workflow, 0.2-second per-iteration think time. Duration requested was30 seconds per phase; cleanup/graceful-stop means actual wall time can be longer.

| Phase | UTC run interval | HTTP requests | Requests/s | Mean ms | p95 ms | p99 ms | Unexpected response rate |
|---|---|---:|---:|---:|---:|---:|---:|
| Baseline | 04:34:51.374–04:35:22.482 | 5460 | 180.61 | 17.19 | 34.59 | 44.10 | 0% |
| Fault: 500ms every fifth request | 04:35:36.017–04:36:07.951 | 2080 | 66.51 | 108.89 | 515.70 | 522.59 | 0% |
| Recovery: fault disabled | 04:36:22.014–04:36:53.103 | 4730 | 155.73 | 26.00 | 54.13 | 64.88 | 0% |

All intervals are **2026-09-21 UTC**. The table is derived directly from preserved k6 JSON: [baseline](evidence/native/baseline.json), [fault](evidence/native/fault.json), [recovery](evidence/native/recovery.json), and [phase boundaries](evidence/native/times.json). Overall k6 metrics include setup readiness traffic; server business metrics exclude it. Deliberate409s are expected only in the designated conflict call. `unexpected_responses` is a k6 Rate of a boolean *unexpected* condition: its raw `fails` count means false observations (expected responses), **not failed test checks**. Check success rate was1 in every phase.

Observed interpretation: the injected wait raised client tails to about half a second and reduced closed-loop throughput. Recovery removed that large delay, but returned neither throughput nor tails to exactly the original baseline. This short shared-host run does not establish why the smaller baseline/recovery difference remained. No optimization or capacity claim is made from it.

Reproduction of the measured native workload, with an already running native API, in PowerShell:

```powershell
$env:BASE_URL='http://127.0.0.1:18000'
$env:DURATION='30s'
$env:PHASE='baseline' # repeat as fault/recovery with server configuration changed
$env:SUMMARY_FILE='results/native-baseline.json'
k6 run load-tests/baseline.js
```

The actual harness also enabled Prometheus remote write to local port19090. Native process restarts separated phases by about14 seconds, **not the 310-second isolation used by the delivered Docker anomaly scripts**. Consequently the native table uses per-run k6 summaries, not mixed 5-minute server quantiles. These results must not be relabeled as a Docker/ELK benchmark or screenshots.

The native API and demo were bound to `127.0.0.1:18000` and `127.0.0.1:18010`; Prometheus to `127.0.0.1:19090`. The validation harness shut down its temporary API/Prometheus/demo processes on completion. PostgreSQL was stopped after the outage/recovery checks; no service is installed. Ignored downloaded binaries may remain for inspection; none are part of the Docker build context.

## Actual concurrency and cardinality evidence

[Concurrency JSON](evidence/native/concurrency.json) contains `booking_winners.count=1` and `booking_rejected.count=19`, plus passed thresholds. The full pytest suite independently checks persisted DB state, direct SQL protection, and cancellation under concurrency.

[Cardinality JSON](evidence/native/cardinality.json) contains actual Prometheus query responses and UTC timestamps from the native run. The high mode query returns100; after restart without the label it returns1. The demo enforces its100-event cap in both modes. Stored older samples remain in the native TSDB; changing exposition does not delete history. This proves the live Prometheus behavior natively, while the provided Docker/PowerShell/Bash wrappers still need a Docker-host execution.

## One actual original booking log

This is an original line produced by the native API during the measured run, also preserved as [JSON](evidence/native/booking-log.json):

```json
{"timestamp":"2026-09-21T04:34:51.362860+00:00","service":"campus-booking","severity":"INFO","message":"request_completed","request_id":"native-evidence-booking-001","method":"POST","route":"/bookings","status_code":201,"duration_ms":17.353,"operation":"http_request"}
```

It proves local JSONL formatting and correlation, **not Filebeat delivery**. Expected searchable fields are the same root fields plus parsed `@timestamp`; the actual indexed document remains **[RUN EXPERIMENT AND INSERT RESULT]**. `scripts/verify-stack.py` checks and prints that real document when the complete stack runs. The [native metrics snapshot](evidence/native/metrics.txt) is actual exposition after recovery/concurrency, not an invented one-request sample.

## Not verified here / required handoff checks

1. Docker image builds and Python3.12 container execution.
2. Full Compose startup/health, including shared-volume permissions, Elasticsearch/Kibana memory use, Filebeat delivery/replay, and Node Exporter Docker Desktop collector visibility.
3. Elasticsearch template acceptance, ILM attachment/rollover and eventual deletion, and actual searchable Kibana fields. Configuration exists, but no live Elasticsearch result is claimed.
4. Grafana rendering and all screenshots; native query syntax success does not prove dashboard appearance.
5. Full two-minute Docker anomaly/recovery and the staged10/25/50/100/200-VU experiment, including resource usage and saturation evidence.
6. Docker stop/restart failure demonstrations and persistence across recreation.

Run the README quick start, `docker compose --profile test run --build --rm tests`, `scripts/setup-kibana.py`, and `scripts/verify-stack.py`, then follow [DEMO-CHECKLIST.md](DEMO-CHECKLIST.md). Save the actual outputs and replace the report's relevant placeholders. No screenshots, Kibana documents, Docker benchmarks, or long-term retention observations were invented.
