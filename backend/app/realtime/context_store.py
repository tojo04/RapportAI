from __future__ import annotations

import asyncio
import json
from collections import OrderedDict, deque
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError


class SessionContextStore(Protocol):
    degraded: bool
    async def start(self, call_id: str) -> None: ...
    async def append(self, call_id: str, item: dict) -> None: ...
    async def recent(self, call_id: str) -> list[dict]: ...
    async def claim_once(self, call_id: str, key: str) -> bool: ...
    async def finish(self, call_id: str) -> None: ...
    async def close(self) -> None: ...


class InMemorySessionContextStore:
    degraded = False

    def __init__(self, max_calls: int = 100, max_items: int = 16):
        self._max_calls = max_calls
        self._max_items = max_items
        self._calls: OrderedDict[str, deque[dict]] = OrderedDict()
        self._dedupe: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def start(self, call_id: str) -> None:
        async with self._lock:
            self._calls[call_id] = deque(maxlen=self._max_items)
            self._dedupe[call_id] = set()
            while len(self._calls) > self._max_calls:
                old, _ = self._calls.popitem(last=False)
                self._dedupe.pop(old, None)

    async def append(self, call_id: str, item: dict) -> None:
        async with self._lock:
            self._calls.setdefault(call_id, deque(maxlen=self._max_items)).append(item)

    async def recent(self, call_id: str) -> list[dict]:
        async with self._lock:
            return list(self._calls.get(call_id, ()))

    async def claim_once(self, call_id: str, key: str) -> bool:
        async with self._lock:
            values = self._dedupe.setdefault(call_id, set())
            if key in values:
                return False
            values.add(key)
            return True

    async def finish(self, call_id: str) -> None:
        async with self._lock:
            self._calls.pop(call_id, None)
            self._dedupe.pop(call_id, None)

    async def close(self) -> None:
        return None


class RedisSessionContextStore:
    degraded = False

    def __init__(self, redis: Redis, max_items: int = 16, active_ttl: int = 3600, completed_ttl: int = 300):
        self._redis = redis
        self._max_items = max_items
        self._active_ttl = active_ttl
        self._completed_ttl = completed_ttl

    def _key(self, call_id: str, kind: str) -> str:
        return f"rapportai:call:{call_id}:{kind}"

    async def start(self, call_id: str) -> None:
        key = self._key(call_id, "context")
        await self._redis.delete(key, self._key(call_id, "dedupe"))
        await self._redis.set(self._key(call_id, "active"), "1", ex=self._active_ttl)

    async def append(self, call_id: str, item: dict) -> None:
        key = self._key(call_id, "context")
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.rpush(key, json.dumps(item, ensure_ascii=False))
            pipe.ltrim(key, -self._max_items, -1)
            pipe.expire(key, self._active_ttl)
            pipe.expire(self._key(call_id, "active"), self._active_ttl)
            await pipe.execute()

    async def recent(self, call_id: str) -> list[dict]:
        return [json.loads(item) for item in await self._redis.lrange(self._key(call_id, "context"), 0, -1)]

    async def claim_once(self, call_id: str, key: str) -> bool:
        result = await self._redis.set(self._key(call_id, f"once:{key}"), "1", nx=True, ex=self._active_ttl)
        return bool(result)

    async def finish(self, call_id: str) -> None:
        keys = [self._key(call_id, "context"), self._key(call_id, "dedupe")]
        async with self._redis.pipeline(transaction=True) as pipe:
            for key in keys:
                pipe.expire(key, self._completed_ttl)
            pipe.delete(self._key(call_id, "active"))
            await pipe.execute()

    async def close(self) -> None:
        await self._redis.aclose()


class ResilientSessionContextStore:
    """Redis first, bounded single-worker memory fallback on outages."""

    def __init__(self, primary: SessionContextStore, fallback: InMemorySessionContextStore):
        self._primary = primary
        self._fallback = fallback
        self.degraded = False

    async def _run(self, method: str, *args: object):
        try:
            result = await getattr(self._primary, method)(*args)
            self.degraded = False
            return result
        except RedisError:
            self.degraded = True
            return await getattr(self._fallback, method)(*args)

    async def start(self, call_id: str) -> None: await self._run("start", call_id)
    async def append(self, call_id: str, item: dict) -> None: await self._run("append", call_id, item)
    async def recent(self, call_id: str) -> list[dict]: return await self._run("recent", call_id)
    async def claim_once(self, call_id: str, key: str) -> bool: return await self._run("claim_once", call_id, key)
    async def finish(self, call_id: str) -> None: await self._run("finish", call_id)

    async def close(self) -> None:
        try:
            await self._primary.close()  # type: ignore[attr-defined]
        finally:
            await self._fallback.close()
