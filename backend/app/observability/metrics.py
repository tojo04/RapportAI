from __future__ import annotations

import math
from collections import Counter, deque
from threading import Lock
from time import monotonic


class PipelineMetrics:
    """Bounded metrics; never records transcript/audio contents or secrets."""

    def __init__(self, max_samples: int = 1000):
        self._max_samples = max_samples
        self._final_at: dict[tuple[str, str], float] = {}
        self._durations: deque[float] = deque(maxlen=max_samples)
        self._counters: Counter[str] = Counter()
        self._gauges: dict[str, int] = {"active_calls": 0, "queue_depth": 0}
        self._lock = Lock()

    def call_started(self) -> None:
        with self._lock: self._gauges["active_calls"] += 1

    def call_ended(self) -> None:
        with self._lock: self._gauges["active_calls"] = max(0, self._gauges["active_calls"] - 1)

    def final_received(self, call_id: str, segment_id: str, at: float | None = None) -> None:
        with self._lock:
            self._final_at[(call_id, segment_id)] = monotonic() if at is None else at
            self._counters["finals"] += 1

    def suggestion_delivered(self, call_id: str, evidence_ids: list[str], at: float | None = None) -> None:
        delivered = monotonic() if at is None else at
        with self._lock:
            starts = [self._final_at.get((call_id, segment_id)) for segment_id in evidence_ids]
            known = [value for value in starts if value is not None]
            if known:
                self._durations.append((delivered - min(known)) * 1000)
            self._counters["suggestions"] += 1

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock: self._counters[name] += amount

    def queue_depth(self, depth: int) -> None:
        with self._lock: self._gauges["queue_depth"] = max(0, depth)

    def snapshot(self) -> dict:
        with self._lock:
            samples = sorted(self._durations)
            return {
                "metric": "transcript_final_received_to_suggestion_delivered_ms",
                "speech_end_latency": "unavailable: no compatible VAD/audio clock boundary",
                "sample_count": len(samples),
                "p50_ms": self._percentile(samples, 0.50),
                "p95_ms": self._percentile(samples, 0.95),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
            }

    @staticmethod
    def _percentile(values: list[float], fraction: float) -> float | None:
        if not values: return None
        index = max(0, math.ceil(len(values) * fraction) - 1)
        return round(values[index], 2)
