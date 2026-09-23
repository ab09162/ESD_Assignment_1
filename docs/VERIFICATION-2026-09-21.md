# Docker verification — 21 September 2026

Real execution on Windows with Docker Desktop Linux containers. The earlier native Windows results are archived in [VERIFICATION-NATIVE.md](VERIFICATION-NATIVE.md). Selected actual evidence is in [evidence/docker](evidence/docker); raw logs remain in ignored `results/`.

## Environment and fixes

Docker Desktop 4.91.0, Engine 29.8.0, Compose 5.5.1, Linux/amd64, 16 CPUs and 16,624,320,512 bytes of Docker memory. App: Python 3.12.10, one Uvicorn worker, PostgreSQL 16.9, connection pool 10 plus 5 overflow, 2-second pool timeout. k6 1.0.0 and the full observability stack shared this machine. These are local measurements, not production capacity guarantees.

Actual integration fixes:

- Test-image PyPI read timeout: dependency installation now allows 120 seconds and three retries.
- Container pytest import failure: test CMD now uses `python -m pytest` so the app package resolves. Every test was preserved.
- Unsupported Node Exporter default collectors: explicitly enabled the required CPU, memory, filesystem, disk, network and supporting collectors; all now report success.
- Windows PowerShell `localhost` fallback took about 2.3 seconds versus 45 ms on `127.0.0.1` in a direct health probe. Cardinality automation now uses the IPv4 loopback address published by Compose for its repeated requests.
- Grafana's whole provisioning-directory mount hid its default plugin/alerting directories and logged provisioning errors. Mounting only the datasource/dashboard subdirectories preserves the image defaults; required provisioning was reverified.
- Kibana logged a missing saved-object encryption key when creating an alerts client. A stable private key was generated only in ignored `.env`; Compose passes it to Kibana, while `.env.example` contains an explicit local placeholder. The alerts-client API now returns 200. This follows [Elastic's saved-object key configuration](https://www.elastic.co/guide/en/kibana/8.19/xpack-security-secure-saved-objects.html).
- Transient k6 registry/DNS/EOF download failures: bounded retries succeeded with the pinned image unchanged.

No booking invariant, pool limit, load threshold or fault size was weakened. Existing `.env` and named data volumes were preserved.

## Functional and observability checks

| Check | Actual result |
|---|---|
| Compose config/build/start | Passed; complete `up --build -d --wait --wait-timeout 300` succeeded |
| Required services | app, postgres, prometheus, grafana, node-exporter, elasticsearch, kibana, filebeat healthy; setup jobs exit 0 normally |
| Endpoints | `/health`, `/ready`, `/metrics`, `/openapi.json`, `/rooms` returned 200; OpenAPI includes the booking API |
| PowerShell smoke | Create 201, fetch, deliberate overlapping 409, cancellation and supplied request ID passed |
| Docker/PostgreSQL suite | **26 passed in 4.43 seconds**, no skips; [output](evidence/docker/pytest.txt) |
| DB invariants | Tests verify 1 winner/19 conflicts, persisted row count, direct SQL overlap rejection, adjacency and idempotent concurrent cancellation |
| Prometheus | App, Node Exporter and self UP; Counter/Gauge/Histogram/Summary data and histogram buckets present |
| Grafana | Default Prometheus datasource healthy; all 3 dashboards, 40 panels and 46 expressions validated; every query returned data during baseline |
| Browser rendering | No browser connected; provisioning/queries verified, visual inspection and screenshots remain manual |
| Kibana | Setup created `campus-logs-*` data view using `@timestamp`; mappings and searchable documents verified |
| Complete logging pipeline | Real app request → JSONL → Filebeat → Elasticsearch; numeric status/duration and correlation preserved |
| Indexed correlation | `verify-eb604ba0-b5a9-49fb-b080-f2c46ad17542`: POST `/bookings`, 201, 12.034 ms |
| ILM | `campus-logs-000001` managed by `campus-logs-7d`, hot rollover policy attached; seven-day deletion not observed |
| Local telemetry loss | Dropped-log and sink-error rates zero in baseline and staged load |

Evidence: [Grafana/Prometheus](evidence/docker/observability-during-baseline.json), [stored log/ILM](evidence/docker/stack-verification.json), [Node/Kibana](evidence/docker/node-and-kibana.json).

## Baseline and increasing-user load

All intervals are UTC on 2026-09-21. Command boundaries include container startup/cleanup; k6 rates use its measured run time. Workload: room/availability reads, create, fetch, deliberate conflicts, cancellation, and 0.2-second iteration think time. k6 totals include setup readiness; server business metrics exclude probes. Deliberate 409s are expected only on designated conflict calls.

| Run | Command interval UTC | HTTP requests | Requests/s | Mean ms | Client p95 ms | Client p99 ms | Unexpected responses |
|---|---|---:|---:|---:|---:|---:|---:|
| 10 VUs, 2 minutes | 09:35:03.466–09:37:06.536 | 18,886 | 157.05 | 25.60 | 50.23 | 63.82 | 0 / 18,885 checked (0%) |
| 10/25/50/100/200 VUs, 13 minutes | 09:37:45.296–09:50:47.462 | 223,460 | 286.48 | 220.92 | 828.67 | 1,388.89 | 271 / 223,459 checked (0.1213%) |

Both passed unchanged whole-run thresholds. **The staged run was not error-free:** aggregate thresholds hide the worse 200-user period. k6's custom unexpected-response Rate stores true observations in `passes` and false observations in `fails`; use its `rate` or the separate `checks` metric to avoid reversing their meaning.

Plateau comparisons below use actual Prometheus samples after at least 60 seconds at stable VUs. They are means of sampled one-minute rates and histogram quantile estimates, not per-stage client percentiles. Dashboard five-minute quantiles mix these short stages.

| VUs | Sample interval UTC | Server req/s | Server p95 / p99 ms | 5xx/s | In flight | DB mean ms | App CPU cores | VM CPU / memory |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 10 | 09:39:20.296–09:40:15.296 | 153.58 | 48.67 / 85.25 | 0 | 5.00 | 18.05 | 0.53 | 8.50% / 19.77% |
| 25 | 09:41:50.296–09:42:45.296 | 215.72 | 230.15 / 407.15 | 0 | 17.08 | 56.17 | 0.95 | 12.58% / 19.86% |
| 50 | 09:44:25.296–09:45:15.296 | 376.36 | 230.33 / 273.83 | 0 | 33.64 | 73.16 | 1.05 | 14.38% / 20.04% |
| 100 | 09:46:50.296–09:47:45.296 | 357.01 | 693.93 / 956.03 | 0 | 85.25 | 196.72 | 1.04 | 14.27% / 20.25% |
| 200 | 09:49:20.296–09:50:15.296 | 333.06 | 1,925.26 / 2,397.61 | 2.07 | 189.08 | 465.36 | 1.04 | 14.27% / 20.60% |

Throughput stopped improving beyond the observed 50-user plateau while waiting/tails rose. At 200 users, pool `TimeoutError` logs correlate with controlled 503s near the configured 2-second wait. Elasticsearch contains 271 business 503s plus one readiness-probe 503 during the load command window. App CPU was near one core while aggregate VM CPU was well below full use. This supports a limit in the current single-worker/pool configuration; it does not isolate SQL execution time or establish an exact sustainable arrival rate. No blind pool enlargement was applied.

Initial-baseline sampled VM CPU averaged 7.28%, VM memory 19.26%, app CPU 0.42 cores, app RSS 75.58 MiB, and repository duration 16.94 ms. These are sample summaries including rate-window boundaries.

Evidence: [baseline](evidence/docker/baseline.json), [load](evidence/docker/load.json), [UTC boundaries](evidence/docker/times.json), [stage samples](evidence/docker/load-stages.json), [baseline resource series](evidence/docker/baseline-prometheus.json), [load series](evidence/docker/load-prometheus.json), [indexed errors](evidence/docker/experiment-logs.json).

## Anomaly, cardinality and final checks

The default PowerShell anomaly script ran three 10-VU, two-minute profiles with 310-second quiet intervals. All timestamps are **2026-09-21 UTC**. Every phase passed unchanged thresholds. CPU/memory are means of sampled VM measurements, not app-only usage.

| Phase | Command interval UTC | HTTP requests | Requests/s | Mean ms | Client p95 ms | Client p99 ms | Unexpected | VM CPU / memory |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 15:32:31.725–15:34:34.224 | 19,346 | 160.93 | 24.06 | 50.22 | 68.51 | 0.00% | 8.37% / 19.57% |
| fault | 15:39:48.301–15:41:52.915 | 7,951 | 65.37 | 113.50 | 519.67 | 528.55 | 0.00% | 5.75% / 19.44% |
| recovery | 15:47:07.301–15:49:10.557 | 18,048 | 150.00 | 28.57 | 58.73 | 74.90 | 0.00% | 7.27% / 19.47% |

Elasticsearch indexed **1,590** `fault_delay_injected` records in the fault interval and none in baseline or recovery. Request `e6b72c73-7092-4008-9ad4-f019f6500802` has the 500 ms injection warning and a matching `GET /bookings/{booking_id}` completion of **508.860 ms**, status 200. This ties the observed slowdown to the deliberate wait. See [indexed correlation](evidence/docker/experiment-logs.json).

Recovery client p95/p99 returned to **58.73/74.90 ms**, with zero unexpected responses and zero new fault logs in the recovery interval. The app was recreated fault-free by script cleanup and readiness returned 200.

Histogram p95 estimates can approach 0.875 seconds when slowed requests fall just above the 0.5-second bucket boundary into the 0.5–1-second bucket. This is interpolation, not evidence that the configured delay became 875 ms; use client percentiles and correlated durations for direct timing.

Evidence: [phase boundaries](evidence/docker/anomaly/times.json), [baseline](evidence/docker/anomaly/baseline.json), [fault](evidence/docker/anomaly/fault.json), [recovery](evidence/docker/anomaly/recovery.json). Corresponding `*-prometheus.json` files preserve exact resource, repository and rate samples.

The actual Docker cardinality script accepted 100 events per mode and Prometheus returned **100 → 1** current value series at **15:49:30.601 → 15:49:39.952 UTC** on 2026-09-21. The total counter value was 100 in each process; the low-mode 101st event returned 429. The low-cardinality demo remains running, and the historical high-cardinality samples remain queryable. [Cardinality evidence](evidence/docker/cardinality.json).

The final Docker k6 concurrency experiment produced **exactly one winner and nineteen clean conflicts**, with all thresholds passed. The PostgreSQL suite independently checked persisted row count and direct SQL protection. [Concurrency evidence](evidence/docker/concurrency.json).

Stopping Grafana and Filebeat together did not prevent a real 201 booking/cancellation. After restart, Filebeat replayed that outage-period request into Elasticsearch. Stopping PostgreSQL produced readiness/rooms 503 while health/metrics stayed 200; starting PostgreSQL restored readiness/rooms 200 **without replacing the app container**. All services were restored. [Outage/recovery evidence](evidence/docker/outage-checks.json).

## Completion checks

Final inspection confirmed all eight required services and the low-cardinality demo running/healthy; both one-shot setup jobs exited 0. The app has fault injection disabled. No inspected container was OOM-killed. The full pipeline verifier passed again after the final Grafana/Kibana configuration fixes. [Health/resources](evidence/docker/final-health.json), [final pipeline](evidence/docker/stack-verification-final.json), [final 46-query check](evidence/docker/observability-final.json), [plugin/alerts-client verification](evidence/docker/observability-config-fixes.json).

All retained service logs were reviewed, with removed app-container history supplemented by indexed experiment evidence. Expected PostgreSQL exclusion errors correspond to deliberate overlapping bookings; connection failures/503s during controlled database stops and high-load pool exhaustion are recorded separately. No unresolved Filebeat delivery failure, Prometheus scrape failure, datasource-query error or application traceback was found. [Classified retained-log evidence](evidence/docker/final-log-review.json).

Remaining observed startup/platform notices are disclosed, not represented as clean logs: Node Exporter's optional udev metadata is absent; Grafana logs duplicate registration of its built-in table plugin, while the plugin registry contains one table entry and every required timeseries plugin/query works. Kibana's unused email, reporting/session-key, AI-assistant license and screenshotting features emit local-development warnings; this lab uses HTTP without production security. Elasticsearch logged bundled-library/inference initialization warnings and large host timer discontinuities **outside the measured load/anomaly windows**. Their exact host cause was not established. No license purchase, security suppression, or log-level filtering was used to hide them.

Final `active_bookings` was 52. High-load failures during cancellation can leave confirmed synthetic bookings; existing database contents were preserved rather than reset to make the gauge zero. Current fault/drop/sink-error counters were zero and the business refresh gauge was healthy. [Final metric samples](evidence/docker/final-application-metrics.json).

Ruff lint and formatting passed for all 32 Python files; Compose configuration and PowerShell parsing passed, and relative documentation links resolve. Git was initialized locally because the folder had no repository. Source, configurations, scripts, documentation and selected actual evidence are included in the local initial commit. `.env` (including the newly generated private Kibana key), environment variants, tools, caches, raw results and Docker named volumes are excluded. The staged-file audit found no non-example environment secrets, private keys or recognizable credential tokens. No pre-existing Git history or remote existed. [Audit evidence](evidence/docker/repository-audit.json) and [include/exclude list](GITHUB-READINESS.md). Nothing has been pushed to GitHub.

## Node Exporter scope

Actual kernel: `6.6.87.2-microsoft-standard-WSL2`; 16 logical CPU series and 16,624,312,320 bytes of Linux memory. CPU/memory describe Docker Desktop's Linux/WSL2 environment, not native Windows telemetry. Filesystems are Linux-visible mounts, including Windows-shared `/mnt/host/c`; this is not general Windows monitoring. Network counters describe the exporter network namespace. The uname nodename is the container name/ID, not the Windows machine identity.

CPU/memory/filesystem/disk/network metrics returned data and all enabled collectors succeeded. Diskstats reports a one-time missing optional `/run/udev/data` metadata directory; measured disk byte counters still work. Shared-machine activity can influence VM measurements.

## Remaining evidence limits

Browser rendering and screenshots require the user's browser; follow the exact [screenshot checklist](DEMO-CHECKLIST.md). Provisioning/query success does not prove visual appearance. Seven-day expiry and prolonged soak behavior were not observed. The 200-user test exposed a real local capacity limit; no production scalability guarantee is made.
