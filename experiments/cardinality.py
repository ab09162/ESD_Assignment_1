"""Separate, deliberately bounded teaching process. No effect on business metrics."""

import os
from uuid import uuid4

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, generate_latest
from starlette.responses import JSONResponse, Response


def create_demo(high: bool):
    app = FastAPI(title="Isolated cardinality demo")
    registry = CollectorRegistry()
    counter = Counter(
        "demo_requests_total",
        "At most 100 demo events per process",
        ["request_id"] if high else [],
        registry=registry,
    )
    app.state.accepted = 0

    @app.get("/health")
    async def health():
        return {"status": "ok", "high_cardinality": high, "accepted": app.state.accepted}

    @app.post("/hit")
    async def hit():
        # No await between check and increment: atomic within this single-worker event loop.
        if app.state.accepted >= 100:
            return JSONResponse({"detail": "100-event demo cap reached"}, status_code=429)
        app.state.accepted += 1
        if high:
            counter.labels(str(uuid4())).inc()
        else:
            counter.inc()
        return {"accepted": app.state.accepted}

    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST})

    return app


app = create_demo(os.getenv("DEMO_HIGH_CARDINALITY", "true").lower() == "true")
