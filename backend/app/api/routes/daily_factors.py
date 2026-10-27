"""Daily factors: one record per day, create, list, read, update and delete.

Every query is filtered by the authenticated user's id. Another user's record
answers 404, so its existence isn't revealed. A second record for the same
day answers 409 (the table allows one per user per day).

A factor that is NULL was not recorded; it is never treated as 0 or "no".
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.models import DailyFactor, User
from app.schemas.daily_log import (
    FACTOR_FIELDS,
    DailyFactorCreate,
    DailyFactorList,
    DailyFactorOut,
    DailyFactorUpdate,
)

router = APIRouter(prefix="/daily-factors", tags=["daily factors"])


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Daily factors not found.")


def _duplicate() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail="There are already daily factors for this day.")


def _get_owned(db: Session, user: User, record_id: uuid.UUID) -> DailyFactor:
    record = db.scalar(select(DailyFactor).where(DailyFactor.id == record_id, DailyFactor.user_id == user.id))
    if record is None:
        raise _not_found()
    return record


def _day_taken(db: Session, user: User, log_date: date, exclude: uuid.UUID | None = None) -> bool:
    query = select(DailyFactor.id).where(DailyFactor.user_id == user.id, DailyFactor.log_date == log_date)
    if exclude is not None:
        query = query.where(DailyFactor.id != exclude)
    return db.scalar(query) is not None


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _duplicate() from None


@router.get("", response_model=DailyFactorList)
def list_daily_factors(
    user: CurrentUser,
    db: DbSession,
    start_date: Annotated[date | None, Query(description="Earliest day (inclusive)")] = None,
    end_date: Annotated[date | None, Query(description="Latest day (inclusive)")] = None,
    limit: Annotated[int, Query(ge=1, le=400)] = 60,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DailyFactorList:
    """The current user's daily factors, most recent day first."""
    conditions = [DailyFactor.user_id == user.id]
    if start_date is not None:
        conditions.append(DailyFactor.log_date >= start_date)
    if end_date is not None:
        conditions.append(DailyFactor.log_date <= end_date)
    total = db.scalar(select(func.count()).select_from(DailyFactor).where(*conditions))
    records = db.scalars(
        select(DailyFactor).where(*conditions).order_by(DailyFactor.log_date.desc()).limit(limit).offset(offset)
    )
    return DailyFactorList(
        items=[DailyFactorOut.model_validate(r) for r in records], total=total, limit=limit, offset=offset
    )


@router.post("", response_model=DailyFactorOut, status_code=status.HTTP_201_CREATED)
def create_daily_factors(body: DailyFactorCreate, user: CurrentUser, db: DbSession) -> DailyFactorOut:
    if _day_taken(db, user, body.log_date):
        raise _duplicate()
    record = DailyFactor(user_id=user.id, **body.model_dump())
    db.add(record)
    _commit(db)
    db.refresh(record)
    return DailyFactorOut.model_validate(record)


@router.get("/{record_id}", response_model=DailyFactorOut)
def read_daily_factors(record_id: uuid.UUID, user: CurrentUser, db: DbSession) -> DailyFactorOut:
    return DailyFactorOut.model_validate(_get_owned(db, user, record_id))


@router.patch("/{record_id}", response_model=DailyFactorOut)
def update_daily_factors(
    record_id: uuid.UUID, body: DailyFactorUpdate, user: CurrentUser, db: DbSession
) -> DailyFactorOut:
    record = _get_owned(db, user, record_id)
    changes = body.model_dump(exclude_unset=True)
    if "log_date" in changes and _day_taken(db, user, changes["log_date"], exclude=record.id):
        raise _duplicate()
    for field, value in changes.items():
        setattr(record, field, value)
    if all(getattr(record, f) is None for f in FACTOR_FIELDS) and record.notes is None:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="record at least one factor or a note")
    record.updated_at = func.now()
    _commit(db)
    db.refresh(record)
    return DailyFactorOut.model_validate(record)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_daily_factors(record_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    db.delete(_get_owned(db, user, record_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
