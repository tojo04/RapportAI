import json
from pathlib import Path

from app.services.sales_detection import DetectionSegment, SalesSignalCandidate, validate_sales_signals


FIXTURES = Path(__file__).parents[1] / "fixtures" / "multilingual"


def test_unicode_roundtrip_and_exact_multilingual_evidence() -> None:
    fixture = json.loads((FIXTURES / "hindi.json").read_text(encoding="utf-8"))
    segments = [DetectionSegment(**item) for item in fixture["segments"]]
    candidate = SalesSignalCandidate(
        category="objection", evidence_segment_ids=["hi-2"],
        evidence_span="बजट से बहुत ज़्यादा", subject="कीमत",
    )
    result = validate_sales_signals([candidate], segments)
    assert result[0].evidence_span == "बजट से बहुत ज़्यादा"
    encoded = json.dumps(result[0].model_dump(), ensure_ascii=False)
    assert "कीमत" in encoded


def test_labeled_fixtures_are_synthetic_and_well_formed() -> None:
    names = {path.name for path in FIXTURES.glob("*.json")}
    assert names == {"english.json", "hindi.json", "hinglish.json", "no_signal.json"}
    for path in FIXTURES.glob("*.json"):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        text = "\n".join(item["text"] for item in fixture["segments"])
        assert all(item["evidence_span"] in text for item in fixture["expected"])
