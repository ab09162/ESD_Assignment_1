Fresh verification: 23 September 2026. Tests 26/26; concurrency 1/19. Current evidence is in VERIFICATION.pdf and docs/evidence/latest. Historical staged-load and outage checks remain explicitly dated in the earlier record. All 15 original screenshots are included in the report appendix.

# Assignment requirement checklist

Status: **Verified Docker** means an actual container/API/Prometheus/Elasticsearch check ran on this machine; **Documented** means an explanation was reviewed. User-captured browser screenshots are included in the report appendix. See `VERIFICATION.md` and the linked raw evidence for exact scope and limits.

| Request section / requirement | Implementation | File/location | How to verify | Status |
|---|---|---|---|---|
| 0 Inspect existing repository, preserve work, OS | Empty repository inspected; Windows PowerShell detected, no prior app overwritten | Verification record | Read environment notes | Verified; prior work preserved |
| 1 Room service and API-only UI | Rooms, availability, create/fetch/list/cancel, conflict, health/ready/metrics, Swagger | `app/api/routes.py` | Smoke + `/docs` | Verified Docker API/smoke; Swagger visual capture manual |
| 2 Mature local stack | Python 3.12/FastAPI/SQLAlchemy async/Postgres + complete requested observability stack/k6 | Dockerfile, requirements, Compose | Full startup | Verified Docker, all required services healthy |
| 3 HTTP/validation/exception handling/UTC | Typed schemas, clean errors, correlation, lifecycle/timeouts | `app/schemas`, `main.py`, middleware | API tests | Verified Docker/PostgreSQL tests |
| 3 Pool, transactions, indexes, schema | Bounded engine pool, short transactions, deterministic versioned initialization | `app/db`, repositories | Integration tests | Verified Docker/PostgreSQL tests |
| 3 No double-booking race | Partial GiST exclusion constraint | `app/db/schema.sql` | 20-way test + direct SQL test | Verified Docker/PostgreSQL tests |
| 4 Performance measurability/bounded labels | Throughput/status/latency/concurrency/DB/business/resource data | Metrics, three dashboards | k6 baseline, Prometheus | Verified Docker baseline and staged load; capacity limit recorded |
| 5 Counter/Gauge/Histogram/Summary | Required metric types plus business and logging health metrics | `app/observability/metrics.py` | `/metrics`, tests, report table | Verified metric types and real samples |
| 5 Business metrics/own exploration | Created/cancelled/conflicts/active/lead time; derived conflict percentage | Service, refresh loop, app dashboard | Flow + conflict traffic | Verified metric types and real samples |
| 6 All sixteen application dashboard items | 20 panels with titles, descriptions, units, legends and queries | `observability/grafana/dashboards/campus-app.json` | Open provisioned dashboard | 20 application panels/queries verified; browser capture manual |
| 7 Throughput/load dashboard | k6 VUs and client tails, server tails/rates, in-flight, resources, DB | `campus-load.json` | Remote-write baseline | 14 load panels/queries verified with real remote write; screenshot included |
| 8 Node Exporter + named measured machine | Linux VM collector mounts and explicit scope limitations | Compose, Prometheus, `campus-node.json`, README | Targets / resource panels | Verified Docker Linux/WSL2 scope and six resource panels |
| 9 Prometheus config/scrapes/storage | 5s scrape, application/node/self/optional demo, named volume | `observability/prometheus/prometheus.yml` | `promtool check config`; targets | Verified config and live targets |
| 10 Structured JSON logs/correlation/privacy | Allowlisted JSON, safe IDs, error IDs, bounded queue, no bodies/secrets | Logging/middleware/main | Unit tests; inspect real file | Verified tests and indexed correlated JSON |
| 11 Filebeat→Elasticsearch→Kibana | Shared volume, NDJSON, explicit typed mapping, data view setup/KQL | Filebeat/Elastic/Kibana config, scripts | Filebeat `test config`; `verify-stack.py`, Discover | Verified Filebeat→Elasticsearch; Kibana view/mappings verified, screenshot included |
| 12 Persistence/retention/ILM | Size rotation, named volumes, daily rollover + seven-day deletion policy | ILM JSON, README/report | `_ilm/explain`; long-duration expiry observation | Volumes and ILM attachment verified; long-term expiry unobserved |
| 13 Metric end-to-end | Exact observation function, value, exposition, scrape/storage/query/panel | Report Part D | Follow one actual sample | Verified actual sample/query; screenshot included |
| 14 Log end-to-end | ID→JSONL→parsed fields→index→KQL; verifier emits real stored hit | Report Part C/D, verifier | Run smoke/verifier + Discover | Verified actual stored hit and request ID; screenshot included |
| 15 Architecture/protocols/storage/failure effects | Mermaid diagrams and eight-component failure matrix | README, report Part D | Read; controlled stop/start | Documented; outage/recovery verified 21 September |
| 16 Five reproducible business k6 tests | Smoke/baseline/load/stress/concurrency; correct expected statuses | `load-tests/` | `k6 inspect`, execute profiles | Five profiles parsed; Docker baseline/load/concurrency and PowerShell smoke executed |
| 17 Increasing users experiment | 10/25/50/100/200 VUs with plateaus; comparison instructions | `load.js`, report E1 | Load dashboard/time ranges | Verified 21 September; not rerun on 23 September |
| 18 Safe anomaly/recovery automation | Local-only delay every fifth business request; PS/Bash cleanup/time ranges | Middleware, anomaly scripts | Run baseline/fault/recovery | Verified Docker baseline/fault/recovery |
| 19 Isolated cardinality experiment | Separate app, hard cap100, restart without label, real query waits | `experiments/cardinality.py`, scripts | Run both modes; count100→1 | Verified actual Docker/Prometheus 100→1 |
| 20 Real concurrency proof | Exactly one winner and nineteen409; DB count; k6 batch | `tests/test_integration.py`, `concurrency.js` | PostgreSQL suite + k6 | Verified Docker/PostgreSQL and final k6 1 winner/19 conflicts |
| 21 Required automated tests | Health/ready/booking lifecycle/validation/conflict/IDs/metrics/errors/timeouts/fault/concurrency | `tests/` | pytest or isolated Compose tests | 26 Docker tests passed, no skips |
| 22 Compose complete services/healthchecks | All eight requested services + deterministic setup/optional tooling | `docker-compose.yml` | `docker compose config`; build/up | Verified build/start/health |
| 23 Local resource stability | Memory limits, ES512MB heap/single node, bounded queues/pool/logs | Compose, configs | `docker stats --no-stream`, load | Measured VM/app resources; no OOM in final containers |
| 24 Observability failure independence | App startup depends only on PostgreSQL; local queued logs and pull metrics | App + Compose; report matrix | Stop Grafana/Filebeat, smoke | Verified 21 September; not repeated during this refresh |
| 25 Complete Windows-friendly README | Exact PowerShell/Bash startup/API/tests/experiments/cleanup/limits | `README.md` | Fresh-clone walkthrough | Docker walkthrough executed; browser visuals manual |
| 26 Report Parts A–E | Detailed metrics table, logs, design, two experiments, honest placeholders | `report.md` | Read alongside evidence | Updated with real Docker observations; all 15 screenshots included |
| 27 Rubric-weighted effort | API kept small; focus metrics/logs/design/experiments | Repository | Compare A10/B30/C25/D20/E15 | Implemented scope |
| 28 Screenshot checklist | Actions and evidence for every required chart/search/experiment | `docs/DEMO-CHECKLIST.md` | Follow checklist | Exact historical browser ranges/panels/KQL supplied; screenshots included |
| 29 Viva questions | All listed concepts in plain technical language | `docs/VIVA-NOTES.md` | Rehearse with code/charts | Documented |
| 30 Troubleshooting | Ports/memory/ES/Kibana/Filebeat/Grafana/targets/DB/volumes/no traffic | README | Run diagnosis commands as needed | Documented; actual integration fixes recorded |
| 31 Safe cleanup/gitignore | down preserves data; -v deletion explained; runtime files ignored | README, `.gitignore`, `.dockerignore` | Inspect instructions | Ignore rules verified; named runtime volumes excluded |
| 32 Security/privacy | Loopback, no personal data/secrets logged, .env excluded, local limitations explicit | README, .env.example, logging | Tests/review; no internet exposure | Local scope reviewed; sensitive runtime files excluded from Git |
| 33 Lint/tests/config/build/start checks | Ruff, pytest, Compose and promtool; dedicated Docker suite | Verification record | Exact recorded commands | Ruff/config/build/start and 26 container tests passed |
| 34 Actual modest performance validation | Native/Compose k6 runner with JSON evidence; no guessed speedup | `results`, verification record | Actual baseline summary | Real Docker baseline/resource results saved |
| 35 No fake evidence | Measured values scoped, placeholders for unexecuted full-stack runs | Report + verification | Trace every number to a saved run | Actual evidence preserved; no fabricated screenshots |
| 36 Clean organization | API/core/DB/repositories/schemas/services/observability/tests/docs/scripts | Repository tree | Inspect files | Implemented |
| 37 Straightforward style | Small functions, no added services without a role, lint/format | App + scripts | Ruff and code review | Lint/format passed |
| 38 Metric/log correctness details A–I | Template/method/status bounds, monotonic clocks, finally cleanup, correlation, scrape/probe exclusion | Middleware + tests | Metric-label/error tests | Verified tests, exposition and live pipeline |
| 39 Database performance | Indexed range exclusion and queries, bounded pagination/pooling, no N+1 | SQL/repository/engine | Integration/load + query inspection | DB invariants verified; pool saturation measured, tuning unclaimed |
| 40 Valid load data | Unique iteration slots, cleanup, controlled409; separate unexpected Rate | `common.js`, concurrency script | Inspect and run k6 | Verified real workload; unexpected responses separate from deliberate conflicts |
| 41 HTTP error classification | 2xx/409/422/5xx separate; explicit server failure rate | App/dashboard/report | Conflict + validation + DB failure | Verified 409s, validation tests and controlled 503s |
| 42 Startup experience | Copy env, build/up, auto DB/Grafana/ES; one deterministic Kibana setup | README, Compose | Fresh Docker host walkthrough | Complete startup/Kibana setup verified |
| 43 Final self-audit | This complete section-numbered table | This file | Compare against pasted request | Updated after real Docker execution |
| 44 Completion report | Commands, files, URLs, remaining checks in final response | Final response + README | Read delivery | Results, limits and manual screenshots documented |
| 45 Autonomous completion and honest errors | Implementation/config/tests/docs/experiments carried through; limitations disclosed | Verification record | Inspect results/pending tasks | Docker work completed; user-captured browser evidence included |

All requested Docker runtime experiments are now recorded with real evidence. Original screenshot evidence is included; source, PDFs and screenshots are ready for submission. Seven-day deletion and production capacity are not claimed.
