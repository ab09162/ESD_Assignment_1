# GitHub readiness audit

Repository: https://github.com/ab09162/ESD_Assignment_1 (branch `main`). Submission PDFs, repeatable PDF generation scripts and selected real evidence are included. Local environment credentials and runtime data remain ignored. The remote was checked before publishing; no force push is used.

All 15 original screenshots in screenshots/ are included in the report as a landscape evidence appendix. PDFs are based on the measured 23 September run; this cleanup does not rerun experiments or change their timestamps.

## Include in the local commit

- Application, real PostgreSQL tests, dependency pins and `pyproject.toml`.
- Dockerfile, Compose, `.env.example`, `.gitignore`, `.dockerignore`, `.gitattributes`.
- All Prometheus, Grafana dashboards/provisioning, Elasticsearch, Filebeat and Kibana configuration.
- PowerShell/Bash/Python scripts, all k6 profiles and the isolated cardinality experiment.
- README, report, verification records, requirement audit, viva notes and exact screenshot checklist.
- Selected actual JSON/text evidence under `docs/evidence/`; `results/.gitkeep` only from the runtime-results folder.

## Exclude

- `.env` and other `.env.*` variants, except the documented `.env.example` placeholder file.
- `.venv/`, `.tools/`, `.tmp/`, Python/test/lint caches, logs and raw `results/` output.
- Docker-managed PostgreSQL, Prometheus, Grafana, Elasticsearch, Filebeat-offset and application-log named volumes. They live in Docker storage, not the repository.
- Local credentials, downloaded binaries, database files, private keys or local-only configuration.

The example passwords `local-coursework-change-me` and `local-test-only`, and the example Kibana encryption key, are explicit local demonstration placeholders. The generated private Kibana key exists only in ignored `.env`. Runtime environment values are not printed into committed verification records. Review evidence for personal data before adding any future real-user workload.

Submission file and screenshot-integrity checks are recorded in `docs/evidence/latest/submission-audit.json`; all PDF render checks are in `docs/evidence/latest/pdf-validation.json`. Original user-captured screenshots are included; no fabricated screenshots are included.
