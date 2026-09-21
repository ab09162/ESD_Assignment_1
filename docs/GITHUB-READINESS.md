# GitHub readiness audit

The working folder had no `.git` directory. A local `main` repository was initialized using the existing Git identity for the audited source/evidence commit. No remote repository was supplied and nothing is pushed to GitHub.

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

Final tracked-file, ignore-rule, content and Git status checks are recorded at completion in `VERIFICATION.md`. Browser screenshots remain a manual submission step; no fabricated screenshots are included.
