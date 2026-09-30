from fastapi import APIRouter, HTTPException, Query, Request, status
from starlette.concurrency import run_in_threadpool

from app.storage.call_repository import CallRepository, PersistenceError


router = APIRouter(prefix="/api/history", tags=["history"])


def _repository(request: Request) -> CallRepository:
    repository = getattr(request.app.state, "call_repository", None)
    if repository is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Call history is not configured.")
    return repository


@router.get("/calls")
async def list_calls(request: Request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)) -> dict:
    try:
        page = await run_in_threadpool(_repository(request).list_calls, offset, limit)
        return {"items": page.items, "offset": page.offset, "limit": page.limit}
    except PersistenceError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/calls/{call_id}")
async def get_call(call_id: str, request: Request) -> dict:
    try:
        call = await run_in_threadpool(_repository(request).get_call, call_id)
    except PersistenceError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if call is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Saved call was not found.")
    return call


@router.post("/calls/{call_id}/analysis/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_analysis(call_id: str, request: Request) -> dict[str, str]:
    if await run_in_threadpool(_repository(request).get_call, call_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Saved call was not found.")
    runner = getattr(request.app.state, "live_analysis_runner", None)
    if runner is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Live analysis is not configured.")
    scheduled = runner.schedule(call_id)
    return {"status": "scheduled" if scheduled else "already_running"}
