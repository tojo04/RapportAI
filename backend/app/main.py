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


settings = get_settings()

app = FastAPI(
    title="RapportAI API",
    description="API for transcribing and analyzing recorded sales calls.",
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
        RedisSessionContextStore(Redis.from_url(settings.redis_url, decode_responses=True)),
        InMemorySessionContextStore(settings.max_retained_live_calls),
    )
    if settings.redis_enabled
    else InMemorySessionContextStore(settings.max_retained_live_calls)
)

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


@app.on_event("startup")
def reconcile_abandoned_calls() -> None:
    repository = app.state.call_repository
    if repository is not None:
        repository.reconcile_abandoned()
        repository.reset_abandoned_analysis()


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
