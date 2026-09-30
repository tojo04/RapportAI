import asyncio

from redis.exceptions import ConnectionError

from app.realtime.context_store import InMemorySessionContextStore, ResilientSessionContextStore


def test_bounded_context_call_isolation_and_atomic_dedupe() -> None:
    async def scenario() -> None:
        store = InMemorySessionContextStore(max_calls=2, max_items=2)
        await store.start("a")
        await store.start("b")
        for value in range(3):
            await store.append("a", {"value": value})
        assert await store.recent("a") == [{"value": 1}, {"value": 2}]
        assert await store.recent("b") == []
        results = await asyncio.gather(*(store.claim_once("a", "event") for _ in range(5)))
        assert results.count(True) == 1
        await store.finish("a")
        assert await store.recent("a") == []
    asyncio.run(scenario())


def test_redis_outage_uses_bounded_memory_fallback() -> None:
    class Failing:
        degraded = False
        async def start(self, call_id: str) -> None: raise ConnectionError("offline")
        async def append(self, call_id: str, item: dict) -> None: raise ConnectionError("offline")
        async def recent(self, call_id: str) -> list[dict]: raise ConnectionError("offline")
        async def claim_once(self, call_id: str, key: str) -> bool: raise ConnectionError("offline")
        async def finish(self, call_id: str) -> None: raise ConnectionError("offline")

    async def scenario() -> None:
        store = ResilientSessionContextStore(Failing(), InMemorySessionContextStore())
        await store.start("call")
        await store.append("call", {"text": "kept"})
        assert await store.recent("call") == [{"text": "kept"}]
        assert store.degraded is True
    asyncio.run(scenario())
