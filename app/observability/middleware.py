import asyncio
import re
from time import perf_counter
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.routing import Match

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
EXCLUDED = {"/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json"}
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"}


def route_template(app, scope):
    partial = None
    for route in app.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route.path
        if match == Match.PARTIAL:
            partial = route.path
    return partial or "unmatched"


class ObservabilityMiddleware:
    def __init__(self, app, owner, settings, metrics):
        self.app, self.owner, self.settings, self.metrics = app, owner, settings, metrics
        self.fault_sequence = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        supplied = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin1")
        request_id = supplied if SAFE_ID.fullmatch(supplied) else str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        route = route_template(self.owner, scope)
        method = scope["method"] if scope["method"] in METHODS else "OTHER"
        measured = route not in EXCLUDED
        metrics = self.metrics
        started, status, response_started = perf_counter(), 500, False
        logger = self.owner.state.logger
        fields = {"request_id": request_id, "method": method, "route": route}

        async def send_with_id(message):
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status, response_started = message["status"], True
                message["headers"] = [
                    (key, value)
                    for key, value in message["headers"]
                    if key.lower() != b"x-request-id"
                ] + [(b"x-request-id", request_id.encode())]
            await send(message)

        async def error(code, detail):
            if not response_started:
                await JSONResponse(
                    {"detail": detail, "request_id": request_id},
                    status_code=code,
                )(scope, receive, send_with_id)

        if measured:
            metrics.in_progress.labels(method, route).inc()
        try:
            async with asyncio.timeout(self.settings.request_timeout_seconds):
                if measured and route != "unmatched" and self.settings.fault_delay_enabled:
                    self.fault_sequence += 1
                    if self.fault_sequence % self.settings.fault_every_n_requests == 0:
                        metrics.faults.inc()
                        logger.warning(
                            "fault_delay_injected",
                            extra={
                                "fields": {
                                    **fields,
                                    "operation": "fault_delay",
                                    "delay_ms": self.settings.fault_delay_ms,
                                }
                            },
                        )
                        await asyncio.sleep(self.settings.fault_delay_ms / 1000)
                await self.app(scope, receive, send_with_id)
        except TimeoutError:
            logger.error(
                "request_timeout", extra={"fields": {**fields, "error_type": "TimeoutError"}}
            )
            await error(504, "Request exceeded its time budget")
        except Exception as exc:
            # Deliberately omit exception strings: SQL/driver messages can contain request data.
            logger.error(
                "request_failed",
                extra={
                    "fields": {
                        **fields,
                        "error_type": type(exc).__name__,
                    }
                },
            )
            await error(500, "Internal server error")
        finally:
            elapsed = perf_counter() - started
            if measured:
                metrics.in_progress.labels(method, route).dec()
                metrics.requests.labels(method, route, str(status)).inc()
                metrics.duration.labels(method, route, str(status)).observe(elapsed)
            if measured or status >= 500:
                logger.log(
                    40 if status >= 500 else 20,
                    "request_completed",
                    extra={
                        "fields": {
                            **fields,
                            "status_code": status,
                            "duration_ms": round(elapsed * 1000, 3),
                            "operation": "http_request",
                        }
                    },
                )
