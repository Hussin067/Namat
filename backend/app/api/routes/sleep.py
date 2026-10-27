"""Sleep logs: one record per night, create, list, read, update and delete.

Every query is filtered by the authenticated user's id. Another user's log
answers 404, so its existence isn't revealed. A second log for the same night
answers 409 (the table allows one per user per night).
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.models import SleepLog, User
from app.schemas.daily_log import SleepLogCreate, SleepLogList, SleepLogOut, SleepLogUpdate, check_sleep_times

router = APIRouter(prefix="/sleep-logs", tags=["sleep"])


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Sleep log not found.")


def _duplicate() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail="There is already a sleep log for this night.")


def _get_owned(db: Session, user: User, log_id: uuid.UUID) -> SleepLog:
    log = db.scalar(select(SleepLog).where(SleepLog.id == log_id, SleepLog.user_id == user.id))
    if log is None:
        raise _not_found()
    return log


def _night_taken(db: Session, user: User, sleep_date: date, exclude: uuid.UUID | None = None) -> bool:
    query = select(SleepLog.id).where(SleepLog.user_id == user.id, SleepLog.sleep_date == sleep_date)
    if exclude is not None:
        query = query.where(SleepLog.id != exclude)
    return db.scalar(query) is not None


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        # A database rule caught something (most likely the same night saved twice at once).
        db.rollback()
        raise _duplicate() from None


@router.get("", response_model=SleepLogList)
def list_sleep_logs(
    user: CurrentUser,
    db: DbSession,
    start_date: Annotated[date | None, Query(description="Earliest night (inclusive)")] = None,
    end_date: Annotated[date | None, Query(description="Latest night (inclusive)")] = None,
    limit: Annotated[int, Query(ge=1, le=400)] = 60,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SleepLogList:
    """The current user's sleep logs, most recent night first."""
    conditions = [SleepLog.user_id == user.id]
    if start_date is not None:
        conditions.append(SleepLog.sleep_date >= start_date)
    if end_date is not None:
        conditions.append(SleepLog.sleep_date <= end_date)
    total = db.scalar(select(func.count()).select_from(SleepLog).where(*conditions))
    logs = db.scalars(
        select(SleepLog).where(*conditions).order_by(SleepLog.sleep_date.desc()).limit(limit).offset(offset)
    )
    return SleepLogList(items=[SleepLogOut.model_validate(log) for log in logs], total=total, limit=limit, offset=offset)


@router.post("", response_model=SleepLogOut, status_code=status.HTTP_201_CREATED)
def create_sleep_log(body: SleepLogCreate, user: CurrentUser, db: DbSession) -> SleepLogOut:
    if _night_taken(db, user, body.sleep_date):
        raise _duplicate()
    log = SleepLog(user_id=user.id, **body.model_dump())
    db.add(log)
    _commit(db)
    db.refresh(log)
    return SleepLogOut.model_validate(log)


@router.get("/{log_id}", response_model=SleepLogOut)
def read_sleep_log(log_id: uuid.UUID, user: CurrentUser, db: DbSession) -> SleepLogOut:
    return SleepLogOut.model_validate(_get_owned(db, user, log_id))


@router.patch("/{log_id}", response_model=SleepLogOut)
def update_sleep_log(log_id: uuid.UUID, body: SleepLogUpdate, user: CurrentUser, db: DbSession) -> SleepLogOut:
    log = _get_owned(db, user, log_id)
    changes = body.model_dump(exclude_unset=True)
    try:
        check_sleep_times(
            changes.get("sleep_date", log.sleep_date),
            changes.get("bedtime", log.bedtime),
            changes.get("wake_time", log.wake_time),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None
    if "sleep_date" in changes and _night_taken(db, user, changes["sleep_date"], exclude=log.id):
        raise _duplicate()
    for field, value in changes.items():
        setattr(log, field, value)
    log.updated_at = func.now()
    _commit(db)
    db.refresh(log)
    return SleepLogOut.model_validate(log)


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sleep_log(log_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    db.delete(_get_owned(db, user, log_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
