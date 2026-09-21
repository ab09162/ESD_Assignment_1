FROM python:3.12.10-slim-bookworm AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN groupadd --gid 10001 campus && useradd --uid 10001 --gid campus --no-create-home campus \
    && mkdir /var/log/campus && chown campus:campus /var/log/campus
COPY app ./app
COPY experiments ./experiments
COPY scripts ./scripts
COPY observability/elasticsearch ./observability/elasticsearch
USER campus
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--timeout-keep-alive", "5", "--timeout-graceful-shutdown", "15", "--limit-concurrency", "512"]

FROM base AS test
USER root
RUN pip install --no-cache-dir --timeout 120 --retries 3 -r requirements-dev.txt
COPY tests ./tests
COPY pyproject.toml ./
USER campus
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
