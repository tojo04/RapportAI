import asyncio

from app.core.config import Settings
from app.models.analysis import CallAnalysis
from app.services.live_analysis import LiveAnalysisRunner


class Repository:
    def __init__(self) -> None:
        self.status = "pending"
        self.result = None
        self.error = None
        self.claims = 0

    def claim_analysis(self, call_id: str, version: str) -> bool:
        self.claims += 1
        if self.status not in {"pending", "failed"}:
            return False
        self.status = "running"
        return True

    def get_call(self, call_id: str) -> dict:
        return {"transcript_segments": [{"text": "Customer needs a CRM and asks about pricing."}]}

    def complete_analysis(self, call_id: str, version: str, result: dict) -> None:
        self.status = "completed"
        self.result = result

    def fail_analysis(self, call_id: str, version: str, message: str) -> None:
        self.status = "failed"
        self.error = message


def settings() -> Settings:
    return Settings(None, None, None, 20, "http://localhost:5173")


def fake_analysis(transcript: str, *, settings: Settings) -> CallAnalysis:
    return CallAnalysis(
        summary="CRM pricing discussion", customer_needs=["CRM"], questions_asked=["Pricing?"],
        objections=[], follow_up_actions=["Send pricing"], sentiment="neutral",
        next_step_confirmed=True, objection_handling_quality=3, discovery_quality=4,
        communication_clarity=5,
    )


def test_live_transcript_reuses_v1_schema_and_scoring() -> None:
    async def scenario() -> None:
        repository = Repository()
        runner = LiveAnalysisRunner(repository, settings(), fake_analysis)
        assert runner.schedule("call-1") is True
        assert runner.schedule("call-1") is False
        await asyncio.sleep(0.05)
        assert repository.status == "completed"
        assert repository.result["score"]["total"] == 85
        assert repository.result["analysis"]["summary"] == "CRM pricing discussion"
        await runner.close()
    asyncio.run(scenario())


def test_insufficient_transcript_is_saved_as_retryable_failure() -> None:
    class ShortRepository(Repository):
        def get_call(self, call_id: str) -> dict:
            return {"transcript_segments": [{"text": "Too short"}]}

    async def scenario() -> None:
        repository = ShortRepository()
        runner = LiveAnalysisRunner(repository, settings(), fake_analysis)
        runner.schedule("call-1")
        await asyncio.sleep(0.05)
        assert repository.status == "failed"
        assert "too short" in repository.error
    asyncio.run(scenario())
