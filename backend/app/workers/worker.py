from typing import Any

import anthropic
from arq.connections import RedisSettings

from app.config import get_settings
from app.db import async_session_factory
from app.workers.tasks import run_evals_for_call

settings = get_settings()


async def startup(ctx: dict[str, Any]) -> None:
    ctx["session_factory"] = async_session_factory
    ctx["anthropic_client"] = (
        anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        if settings.anthropic_api_key
        else None
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    client = ctx.get("anthropic_client")
    if client is not None:
        await client.close()


class WorkerSettings:
    functions = [run_evals_for_call]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
