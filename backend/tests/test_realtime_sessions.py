import asyncio

import pytest

from app.models.realtime import CallState
from app.realtime.sessions import LiveCallCapacityError, LiveCallStore


def test_store_enforces_active_call_limit() -> None:
    async def scenario() -> None:
        store = LiveCallStore(max_active_calls=1)
        await store.create()

        with pytest.raises(LiveCallCapacityError):
            await store.create()

    asyncio.run(scenario())


def test_terminal_calls_do_not_consume_active_capacity() -> None:
    async def scenario() -> None:
        store = LiveCallStore(max_active_calls=1)
        first = await store.create()
        first.state = CallState.ENDED

        second = await store.create()

        assert second.call_id != first.call_id

    asyncio.run(scenario())


def test_store_evicts_oldest_terminal_call_at_retention_limit() -> None:
    async def scenario() -> None:
        store = LiveCallStore(max_active_calls=1, max_retained_calls=1)
        first = await store.create()
        first.state = CallState.ENDED

        second = await store.create()

        assert await store.get(first.call_id) is None
        assert await store.get(second.call_id) is second

    asyncio.run(scenario())


def test_command_idempotency_history_is_bounded() -> None:
    async def scenario() -> None:
        store = LiveCallStore(max_active_calls=1, max_command_history=2)
        session = await store.create()

        async with session.lock:
            session.remember_command("one", "ping")
            session.remember_command("two", "ping")
            session.remember_command("three", "ping")

        assert session.processed_commands == {
            "two": "ping",
            "three": "ping",
        }

    asyncio.run(scenario())
