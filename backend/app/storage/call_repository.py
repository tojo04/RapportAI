from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models.realtime import (
    CallEndedEvent,
    CallStartedEvent,
    CoachSuggestionEvent,
    SalesEvent,
    ServerEvent,
    TranscriptFinalEvent,
)
from app.storage.database import session_scope
from app.storage.models import CallRecord, SalesEventRecord, SuggestionRecord, TranscriptSegmentRecord


class PersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class CallPage:
    items: list[dict]
    offset: int
    limit: int


class CallRepository:
    def __init__(self, sessions: sessionmaker[Session]):
        self._sessions = sessions

    def create_call(self, call_id: str) -> None:
        try:
            with session_scope(self._sessions) as session:
                session.add(CallRecord(call_id=call_id, status="idle", transcript_complete=False, analysis_status="pending"))
        except SQLAlchemyError as exc:
            raise PersistenceError("The call could not be saved.") from exc

    def record_event(self, event: ServerEvent) -> None:
        payload = event.payload.model_dump(mode="json")
        try:
            with session_scope(self._sessions) as session:
                if isinstance(event, TranscriptFinalEvent):
                    statement = insert(TranscriptSegmentRecord).values(
                        call_id=event.call_id, segment_id=event.payload.segment_id,
                        segment_order=event.payload.order, text=event.payload.text,
                        language=event.payload.language, speaker_role=event.payload.speaker_role,
                    ).on_conflict_do_nothing(index_elements=["call_id", "segment_id"])
                    session.execute(statement)
                elif isinstance(event, SalesEvent):
                    session.execute(insert(SalesEventRecord).values(
                        sales_event_id=event.payload.sales_event_id, call_id=event.call_id,
                        event_order=event.seq, payload=payload,
                    ).on_conflict_do_nothing(index_elements=["sales_event_id"]))
                elif isinstance(event, CoachSuggestionEvent):
                    session.execute(insert(SuggestionRecord).values(
                        suggestion_id=event.payload.suggestion_id, call_id=event.call_id,
                        suggestion_order=event.seq, payload=payload,
                    ).on_conflict_do_nothing(index_elements=["suggestion_id"]))
                elif isinstance(event, CallStartedEvent):
                    session.execute(update(CallRecord).where(CallRecord.call_id == event.call_id).values(status="live"))
                elif isinstance(event, CallEndedEvent):
                    session.execute(update(CallRecord).where(CallRecord.call_id == event.call_id).values(
                        status=event.payload.state.value, transcript_complete=event.payload.transcript_complete
                    ))
        except SQLAlchemyError as exc:
            raise PersistenceError("A live call update could not be saved.") from exc

    def reconcile_abandoned(self) -> int:
        with session_scope(self._sessions) as session:
            result = session.execute(update(CallRecord).where(CallRecord.status.in_(["idle", "connecting", "live", "stopping"])).values(status="interrupted", transcript_complete=False))
            return result.rowcount or 0

    def list_calls(self, offset: int = 0, limit: int = 20) -> CallPage:
        with session_scope(self._sessions) as session:
            rows = session.execute(select(CallRecord).order_by(CallRecord.created_at.desc()).offset(offset).limit(limit)).scalars().all()
            return CallPage([self._summary(row) for row in rows], offset, limit)

    def get_call(self, call_id: str) -> dict | None:
        with session_scope(self._sessions) as session:
            call = session.get(CallRecord, call_id)
            if call is None:
                return None
            segments = session.execute(select(TranscriptSegmentRecord).where(TranscriptSegmentRecord.call_id == call_id).order_by(TranscriptSegmentRecord.segment_order)).scalars().all()
            events = session.execute(select(SalesEventRecord).where(SalesEventRecord.call_id == call_id).order_by(SalesEventRecord.event_order)).scalars().all()
            suggestions = session.execute(select(SuggestionRecord).where(SuggestionRecord.call_id == call_id).order_by(SuggestionRecord.suggestion_order)).scalars().all()
            result = self._summary(call)
            result.update({
                "transcript_segments": [{"segment_id": x.segment_id, "order": x.segment_order, "text": x.text, "language": x.language, "speaker_role": x.speaker_role} for x in segments],
                "sales_events": [x.payload for x in events],
                "suggestions": [x.payload for x in suggestions],
                "analysis": call.analysis_result,
                "analysis_error": call.analysis_error,
            })
            return result

    def claim_analysis(self, call_id: str, version: str) -> bool:
        with session_scope(self._sessions) as session:
            result = session.execute(
                update(CallRecord)
                .where(
                    CallRecord.call_id == call_id,
                    CallRecord.analysis_status.in_(["pending", "failed"]),
                )
                .values(
                    analysis_status="running",
                    analysis_version=version,
                    analysis_error=None,
                )
            )
            return (result.rowcount or 0) == 1

    def complete_analysis(self, call_id: str, version: str, result: dict) -> None:
        with session_scope(self._sessions) as session:
            updated = session.execute(
                update(CallRecord)
                .where(
                    CallRecord.call_id == call_id,
                    CallRecord.analysis_status == "running",
                    CallRecord.analysis_version == version,
                )
                .values(analysis_status="completed", analysis_result=result, analysis_error=None)
            )
            if (updated.rowcount or 0) != 1:
                raise PersistenceError("The analysis claim is no longer current.")

    def fail_analysis(self, call_id: str, version: str, message: str) -> None:
        with session_scope(self._sessions) as session:
            session.execute(
                update(CallRecord)
                .where(CallRecord.call_id == call_id, CallRecord.analysis_version == version)
                .values(analysis_status="failed", analysis_error=message[:1000])
            )

    def reset_abandoned_analysis(self) -> int:
        with session_scope(self._sessions) as session:
            result = session.execute(
                update(CallRecord)
                .where(CallRecord.analysis_status == "running")
                .values(analysis_status="failed", analysis_error="Analysis was interrupted by a backend restart.")
            )
            return result.rowcount or 0

    @staticmethod
    def _summary(call: CallRecord) -> dict:
        return {
            "call_id": call.call_id, "status": call.status,
            "transcript_complete": call.transcript_complete,
            "analysis_status": call.analysis_status,
            "analysis_version": call.analysis_version,
            "created_at": call.created_at.isoformat(), "updated_at": call.updated_at.isoformat(),
        }
