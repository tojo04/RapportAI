import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.realtime import router as realtime_router
from app.api.routes import router
from app.api.history import router as history_router
from app.core.config import get_settings
from app.realtime.sessions import LiveCallStore
from app.storage.call_repository import CallRepository
from app.storage.database import create_database_engine, create_session_factory
from app.services.live_analysis import LiveAnalysisRunner
from app.realtime.context_store import InMemorySessionContextStore, RedisSessionContextStore, ResilientSessionContextStore
from redis.asyncio import Redis
from app.observability.metrics import PipelineMetrics


settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    repository = application.state.call_repository
    if repository is not None:
        await asyncio.to_thread(repository.reconcile_abandoned)
        await asyncio.to_thread(repository.reset_abandoned_analysis)
    try:
        yield
    finally:
        runner = application.state.live_analysis_runner
        if runner is not None:
            await runner.close()
        await application.state.session_context_store.close()

app = FastAPI(
    title="RapportAI API",
    description="API for transcribing and analyzing recorded sales calls.",
    lifespan=lifespan,
)

app.state.live_call_store = LiveCallStore(
    settings.max_active_live_calls,
    settings.max_retained_live_calls,
    settings.live_command_history_size,
)
app.state.call_repository = (
    CallRepository(create_session_factory(create_database_engine(settings.database_url)))
    if settings.persistence_enabled
    else None
)
app.state.live_analysis_runner = (
    LiveAnalysisRunner(app.state.call_repository, settings)
    if app.state.call_repository is not None
    else None
)
app.state.session_context_store = (
    ResilientSessionContextStore(
        RedisSessionContextStore(
            Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
        ),
        InMemorySessionContextStore(settings.max_retained_live_calls),
    )
    if settings.redis_enabled
    else InMemorySessionContextStore(settings.max_retained_live_calls)
)
app.state.pipeline_metrics = PipelineMetrics()

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.browser_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(realtime_router)
app.include_router(history_router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/metrics/live")
def live_metrics() -> dict:
    return app.state.pipeline_metrics.snapshot()
