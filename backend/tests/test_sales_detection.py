import asyncio

import pytest

from app.services.sales_detection import (
    DetectionError,
    DetectionSegment,
    FakeSalesEventClassifier,
    LiveSalesDetector,
    SalesSignalCandidate,
    validate_sales_signals,
)


def candidate(
    category: str,
    segment_id: str,
    evidence: str,
    subject: str,
) -> SalesSignalCandidate:
    return SalesSignalCandidate.model_validate(
        {
            "category": category,
            "evidence_segment_ids": [segment_id],
            "evidence_span": evidence,
            "subject": subject,
            "details": [],
        }
    )


def test_evidence_ids_and_exact_spans_are_validated() -> None:
    segments = [
        DetectionSegment(segment_id="s1", order=0, text="What is the price?")
    ]
    valid = validate_sales_signals(
        [candidate("question", "s1", "What is the price?", "price")],
        segments,
    )
    assert valid[0].category == "question"

    with pytest.raises(DetectionError, match="unknown"):
        validate_sales_signals(
            [candidate("question", "missing", "price", "price")],
            segments,
        )
    with pytest.raises(DetectionError, match="absent"):
        validate_sales_signals(
            [candidate("question", "s1", "invented evidence", "price")],
            segments,
        )


def test_quiet_trailing_window_emits_question_not_objection() -> None:
    async def scenario() -> tuple[list[object], FakeSalesEventClassifier]:
        classifier = FakeSalesEventClassifier(
            [[candidate("question", "s1", "Does it support SSO?", "SSO support")]]
        )
        emitted: list[object] = []
        warnings: list[str] = []
        detector = LiveSalesDetector(
            classifier=classifier,
            event_sink=lambda event: _append(emitted, event),
            warning_sink=lambda warning: _append(warnings, warning),
            trailing_seconds=0.001,
        )
        await detector.start()
        await detector.submit(
            DetectionSegment(
                segment_id="s1", order=0, text="Does it support SSO?"
            )
        )
        await detector.flush()
        await detector.close()
        assert warnings == []
        return emitted, classifier

    emitted, classifier = asyncio.run(scenario())
    assert [event.category for event in emitted] == ["question"]
    assert len(classifier.calls) == 1


def test_multiple_types_deduplicate_overlap_but_allow_new_repeated_objection() -> None:
    async def scenario() -> list[object]:
        first = [
            candidate("pricing", "s1", "$99", "Growth price"),
            candidate("objection", "s1", "too expensive", "price concern"),
        ]
        overlap = [candidate("pricing", "s1", "$99", "Growth price")]
        repeated = [
            candidate("objection", "s2", "still too expensive", "price concern")
        ]
        classifier = FakeSalesEventClassifier([first, overlap, repeated])
        emitted: list[object] = []
        detector = LiveSalesDetector(
            classifier=classifier,
            event_sink=lambda event: _append(emitted, event),
            warning_sink=lambda _warning: _noop(),
            trigger_segments=1,
            trailing_seconds=0,
        )
        await detector.start()
        await detector.submit(
            DetectionSegment(
                segment_id="s1", order=0, text="$99 is too expensive"
            )
        )
        while len(classifier.calls) < 1:
            await asyncio.sleep(0)
        await detector.submit(
            DetectionSegment(segment_id="context", order=1, text="Understood")
        )
        while len(classifier.calls) < 2:
            await asyncio.sleep(0)
        await detector.submit(
            DetectionSegment(
                segment_id="s2", order=2, text="It is still too expensive"
            )
        )
        await detector.flush()
        await detector.close()
        return emitted

    emitted = asyncio.run(scenario())
    assert [event.category for event in emitted] == [
        "pricing",
        "objection",
        "objection",
    ]


def test_schema_failure_warns_and_later_window_continues() -> None:
    class FailingOnceClassifier(FakeSalesEventClassifier):
        async def classify(self, segments):  # type: ignore[no-untyped-def]
            if not self.calls:
                self.calls.append(list(segments))
                raise DetectionError("provider details")
            return await super().classify(segments)

    async def scenario() -> list[str]:
        classifier = FailingOnceClassifier([[]])
        warnings: list[str] = []
        detector = LiveSalesDetector(
            classifier=classifier,
            event_sink=lambda _event: _noop(),
            warning_sink=lambda warning: _append(warnings, warning),
            trigger_segments=1,
            trailing_seconds=0,
        )
        await detector.start()
        await detector.submit(DetectionSegment(segment_id="s1", order=0, text="Hi"))
        while not warnings:
            await asyncio.sleep(0)
        await detector.submit(
            DetectionSegment(segment_id="s2", order=1, text="Still here")
        )
        await detector.flush()
        await detector.close()
        return warnings

    assert asyncio.run(scenario()) == ["Sales signal detection was unavailable."]


async def _append(items: list, item: object) -> None:  # type: ignore[type-arg]
    items.append(item)


async def _noop() -> None:
    return None
