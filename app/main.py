import asyncio
from contextlib import asynccontextmanager, suppress
from time import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.api.routes import router
from app.core.config import Settings
from app.db.engine import initialize_schema, make_engine
from app.observability.logging import LogRuntime
from app.observability.metrics import Metrics
from app.observability.middleware import ObservabilityMiddleware
from app.repositories.bookings import BookingRepository
from app.services.bookings import BookingService, DomainError


async def refresh_business_metrics(app):
    while True:
        try:
            count = await app.state.repo.active_count()
            app.state.metrics.active.set(count)
            app.state.metrics.refresh_ok.set(1)
            app.state.metrics.refresh_timestamp.set(time())
        except (SQLAlchemyError, OSError, TimeoutError):
            app.state.metrics.refresh_ok.set(0)
            app.state.logger.warning(
                "business_metrics_refresh_failed",
                extra={
                    "fields": {
                        "operation": "active_count",
                        "error_type": "DatabaseUnavailable",
                    }
                },
            )
        await asyncio.sleep(5)


def create_app(settings: Settings | None = None, repository=None):
    settings = settings or Settings()
    metrics = Metrics()

    @asynccontextmanager
    async def lifespan(app):
        runtime = LogRuntime(settings.log_file, settings.log_queue_size, metrics)
        app.state.logger = runtime.logger
        engine, refresher = None, None
        try:
            if repository is None:
                engine = make_engine(settings)
                await initialize_schema(engine)
                app.state.repo = BookingRepository(engine, metrics)
            else:
                app.state.repo = repository
            app.state.service = BookingService(app.state.repo, metrics)
            refresher = asyncio.create_task(refresh_business_metrics(app))
            runtime.logger.info("application_started", extra={"fields": {"operation": "startup"}})
            yield
        finally:
            if refresher:
                refresher.cancel()
                with suppress(asyncio.CancelledError):
                    await refresher
            if engine:
                await engine.dispose()
            runtime.logger.info("application_stopped", extra={"fields": {"operation": "shutdown"}})
            await asyncio.to_thread(runtime.close)

    app = FastAPI(
        title="Campus Room Booking Service",
        version="1.0.0",
        lifespan=lifespan,
        description="Local observability lab. UTC, half-open booking intervals; no authentication.",
    )
    app.state.metrics = metrics
    app.include_router(router)

    def response(request, code, detail):
        return JSONResponse(
            {"detail": detail, "request_id": request.state.request_id}, status_code=code
        )

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return response(request, exc.status, exc.detail)

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def validation_error(request: Request, exc):
        # Never echo input values (including potentially sensitive unexpected fields).
        errors = [{"location": list(item["loc"]), "message": item["msg"]} for item in exc.errors()]
        return response(request, 422, errors)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc):
        result = response(request, exc.status_code, exc.detail)
        result.headers.update(exc.headers or {})
        return result

    @app.exception_handler(DBAPIError)
    @app.exception_handler(PoolTimeout)
    @app.exception_handler(OSError)
    async def database_error(request: Request, exc):
        app.state.logger.error(
            "database_unavailable",
            extra={
                "fields": {
                    "request_id": request.state.request_id,
                    "operation": "database",
                    "error_type": type(exc).__name__,
                }
            },
        )
        result = response(request, 503, "Database temporarily unavailable; retry shortly")
        result.headers["Retry-After"] = "2"
        return result

    app.add_middleware(ObservabilityMiddleware, owner=app, settings=settings, metrics=metrics)
    return app


app = create_app()
