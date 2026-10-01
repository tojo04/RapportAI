import asyncio

from app.api.realtime import _enqueue
from app.core.config import Settings
from app.models.realtime import CallStartedEvent, CallStartedPayload, CallState, WarningEvent
from app.realtime.sessions import LiveCallSession
from app.storage.call_repository import PersistenceError


def test_failed_durable_write_emits_visible_not_saved_warning() -> None:
    async def scenario() -> None:
        session = LiveCallSession("call-1", 8, state=CallState.LIVE)
        session.outbound_queue = asyncio.Queue(maxsize=4)

        async def fail(_event: object) -> None:
            raise PersistenceError("offline")

        session.persistence_sink = fail
        event = CallStartedEvent(
            call_id="call-1",
            seq=1,
            payload=CallStartedPayload(
                state=CallState.LIVE,
                command_id="start-1",
            ),
        )
        await _enqueue(
            session,
            event,
            Settings(None, None, None, 20, "http://localhost:5173"),
        )
        assert session.persistence_failed is True
        assert await session.outbound_queue.get() is event
        warning = await session.outbound_queue.get()
        assert isinstance(warning, WarningEvent)
        assert warning.payload.code == "persistence_failed"
        assert "not confirmed saved" in warning.payload.message

    asyncio.run(scenario())
