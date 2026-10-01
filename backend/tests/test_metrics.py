from app.observability.metrics import PipelineMetrics


def test_named_end_to_end_metric_and_percentiles() -> None:
    metrics = PipelineMetrics()
    for index, duration in enumerate([0.1, 0.2, 0.3, 0.4, 0.5]):
        metrics.final_received("call", str(index), at=10.0)
        metrics.suggestion_delivered("call", [str(index)], at=10.0 + duration)
    snapshot = metrics.snapshot()
    assert snapshot["sample_count"] == 5
    assert snapshot["p50_ms"] == 300.0
    assert snapshot["p95_ms"] == 500.0
    assert snapshot["speech_end_latency"].startswith("unavailable")


def test_metrics_are_bounded_and_calls_never_go_negative() -> None:
    metrics = PipelineMetrics(max_samples=2)
    metrics.call_ended()
    for index in range(4):
        metrics.final_received("call", str(index), at=1.0)
        metrics.suggestion_delivered("call", [str(index)], at=1.1)
    snapshot = metrics.snapshot()
    assert snapshot["sample_count"] == 2
    assert snapshot["gauges"]["active_calls"] == 0
