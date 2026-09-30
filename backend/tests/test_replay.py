import asyncio
from pathlib import Path

from app.realtime.replay import load_replay_fixture, replay_fixture


FIXTURES = Path(__file__).parents[1] / "fixtures" / "replay"


def test_demo_replay_replaces_partial_deduplicates_and_preserves_order() -> None:
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    fixture = load_replay_fixture(FIXTURES / "demo.json")
    events = asyncio.run(replay_fixture(fixture, sleep=fake_sleep))

    assert delays == [0.005]
    assert [event.type for event in events] == [
        "transcript.partial",
        "transcript.final",
        "transcript.final",
        "transcript.final",
        "transcript.final",
    ]
    finals = sorted(
        (event for event in events if event.type == "transcript.final"),
        key=lambda event: event.payload.order,
    )
    assert [event.payload.segment_id for event in finals] == [
        "demo-1",
        "demo-2",
        "demo-3",
        "demo-4",
    ]
    assert all(event.payload.speaker_role == "unknown" for event in events)
    assert fixture.expected_sales_signals == [
        "question",
        "pricing",
        "competitor",
        "requirement",
        "buying_signal",
    ]


def test_no_signal_and_repeated_objection_fixtures_are_explicit() -> None:
    no_signal = load_replay_fixture(FIXTURES / "no_signal.json")
    repeated = load_replay_fixture(FIXTURES / "repeated_objection.json")

    assert no_signal.expected_sales_signals == []
    assert repeated.expected_sales_signals == ["objection", "objection"]
    events = asyncio.run(replay_fixture(repeated))
    assert [event.payload.segment_id for event in events] == [
        "repeat-1",
        "repeat-2",
    ]
