import argparse
import asyncio
import json
from pathlib import Path

from app.core.config import get_settings
from app.services.sales_detection import DetectionSegment, OpenAISalesEventClassifier, validate_sales_signals


async def main() -> None:
    parser = argparse.ArgumentParser(description="Opt-in real multilingual text reasoning evaluation.")
    parser.add_argument("--real", action="store_true", required=True, help="Acknowledge that this makes billable API calls.")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.openai_api_key or not settings.live_classification_model:
        parser.error("OPENAI_API_KEY and LIVE_CLASSIFICATION_MODEL are required")
    classifier = OpenAISalesEventClassifier(api_key=settings.openai_api_key, model=settings.live_classification_model)
    root = Path(__file__).parents[1] / "fixtures" / "multilingual"
    for path in sorted(root.glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        segments = [DetectionSegment(**item) for item in fixture["segments"]]
        try:
            actual = validate_sales_signals(await classifier.classify(segments), segments)
            print(f"{path.name}: {len(actual)} validated signals (expected {len(fixture['expected'])})")
        except Exception as exc:
            print(f"{path.name}: failed safely: {type(exc).__name__}")


if __name__ == "__main__":
    asyncio.run(main())
