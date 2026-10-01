import argparse
import json
import platform
import random

from app.observability.metrics import PipelineMetrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded fake-provider pipeline timing benchmark.")
    parser.add_argument("--samples", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.samples <= 10000:
        parser.error("samples must be between 1 and 10000")
    random.seed(20260930)
    metrics = PipelineMetrics(max_samples=args.samples)
    for index in range(args.samples):
        start = index * 2.0
        fake_duration = random.uniform(0.02, 0.08)
        metrics.final_received("fake", str(index), at=start)
        metrics.suggestion_delivered("fake", [str(index)], at=start + fake_duration)
    print(json.dumps({"environment": f"{platform.system()} {platform.release()}, Python {platform.python_version()}", "provider": "deterministic simulated fake (no IO)", **metrics.snapshot()}, indent=2))


if __name__ == "__main__":
    main()
