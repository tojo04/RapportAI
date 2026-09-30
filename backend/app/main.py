from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.realtime import router as realtime_router
from app.api.routes import router
from app.core.config import get_settings
from app.realtime.sessions import LiveCallStore


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.browser_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(realtime_router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
