from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings


def make_engine(settings: Settings):
    return create_async_engine(
        settings.db_url(),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            "timeout": 3,
            "command_timeout": 5,
            "server_settings": {
                "statement_timeout": str(settings.db_statement_timeout_ms),
                "lock_timeout": "2000",
                "idle_in_transaction_session_timeout": "5000",
                "timezone": "UTC",
                "application_name": "campus-booking",
            },
        },
    )


async def initialize_schema(engine):
    """Version 1 bootstrap serialized across starters; future changes require migrations."""
    async with engine.begin() as connection:
        await connection.execute(text("SELECT pg_advisory_xact_lock(824701)"))
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        for statement in schema.split(";"):
            if statement.strip():
                await connection.execute(text(statement))
        version = await connection.scalar(text("SELECT max(version) FROM schema_version"))
        if version != 1:
            raise RuntimeError("Unsupported schema version")
