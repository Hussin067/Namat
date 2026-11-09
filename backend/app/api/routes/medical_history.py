"""Medical history the user reports: conditions, allergies, procedures and notes.

Every query is filtered by the authenticated user's id; another user's record
answers 404, so its existence isn't revealed. Nothing here is logged: the
records (and especially the notes) are health information.

    GET    /medical-history                      everything at once
    GET    /medical-history/conditions           list (optionally ?category=)
    POST   /medical-history/conditions           create
    GET    /medical-history/conditions/{id}      read
    PATCH  /medical-history/conditions/{id}      partial update
    DELETE /medical-history/conditions/{id}      delete
    ... the same for /allergies and /procedures
    GET    /medical-history/notes                additional notes
    PUT    /medical-history/notes                replace (empty removes them)
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.models import MedicalAllergy, MedicalCondition, MedicalNotes, MedicalProcedure, User
from app.schemas.medical_history import (
    AllergyCreate,
    AllergyOut,
    AllergyUpdate,
    Category,
    ConditionCreate,
    ConditionOut,
    ConditionUpdate,
    MedicalHistoryOut,
    NotesIn,
    NotesOut,
    ProcedureCreate,
    ProcedureOut,
    ProcedureUpdate,
)

router = APIRouter(prefix="/medical-history", tags=["medical history"])

# A generous ceiling per list, so one account can't grow without bound.
MAX_ITEMS_PER_LIST = 200

ORDER = {
    MedicalCondition: (MedicalCondition.created_at, MedicalCondition.id),
    MedicalAllergy: (MedicalAllergy.created_at, MedicalAllergy.id),
    MedicalProcedure: (MedicalProcedure.created_at, MedicalProcedure.id),
}


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Medical history item not found.")


def _get_owned(db: Session, user: User, model, item_id: uuid.UUID):
    item = db.scalar(select(model).where(model.id == item_id, model.user_id == user.id))
    if item is None:
        raise _not_found()
    return item


def _list(db: Session, user: User, model, *conditions):
    return db.scalars(select(model).where(model.user_id == user.id, *conditions).order_by(*ORDER[model])).all()


def _create(db: Session, user: User, model, body: BaseModel):
    count = db.scalar(select(func.count()).select_from(model).where(model.user_id == user.id))
    if count >= MAX_ITEMS_PER_LIST:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This list is full. Remove an item before adding another.")
    item = model(user_id=user.id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _update(db: Session, user: User, model, item_id: uuid.UUID, body: BaseModel):
    item = _get_owned(db, user, model, item_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    item.updated_at = func.now()
    db.commit()
    db.refresh(item)
    return item


def _delete(db: Session, user: User, model, item_id: uuid.UUID) -> Response:
    db.delete(_get_owned(db, user, model, item_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _notes_out(row: MedicalNotes | None) -> NotesOut:
    return NotesOut(notes=row.notes if row else None, updated_at=row.updated_at if row else None)


def _get_notes(db: Session, user: User) -> MedicalNotes | None:
    return db.scalar(select(MedicalNotes).where(MedicalNotes.user_id == user.id))


@router.get("", response_model=MedicalHistoryOut)
def read_medical_history(user: CurrentUser, db: DbSession) -> MedicalHistoryOut:
    """Every item the user reported, oldest first in each list."""
    return MedicalHistoryOut(
        conditions=[ConditionOut.model_validate(c) for c in _list(db, user, MedicalCondition)],
        allergies=[AllergyOut.model_validate(a) for a in _list(db, user, MedicalAllergy)],
        procedures=[ProcedureOut.model_validate(p) for p in _list(db, user, MedicalProcedure)],
        notes=_notes_out(_get_notes(db, user)),
    )


# --- Conditions -------------------------------------------------------------

@router.get("/conditions", response_model=list[ConditionOut])
def list_conditions(
    user: CurrentUser, db: DbSession, category: Annotated[Category | None, Query()] = None
) -> list[ConditionOut]:
    filters = [MedicalCondition.category == category] if category else []
    return [ConditionOut.model_validate(c) for c in _list(db, user, MedicalCondition, *filters)]


@router.post("/conditions", response_model=ConditionOut, status_code=status.HTTP_201_CREATED)
def create_condition(body: ConditionCreate, user: CurrentUser, db: DbSession) -> ConditionOut:
    return ConditionOut.model_validate(_create(db, user, MedicalCondition, body))


@router.get("/conditions/{item_id}", response_model=ConditionOut)
def read_condition(item_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ConditionOut:
    return ConditionOut.model_validate(_get_owned(db, user, MedicalCondition, item_id))


@router.patch("/conditions/{item_id}", response_model=ConditionOut)
def update_condition(item_id: uuid.UUID, body: ConditionUpdate, user: CurrentUser, db: DbSession) -> ConditionOut:
    return ConditionOut.model_validate(_update(db, user, MedicalCondition, item_id, body))


@router.delete("/conditions/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_condition(item_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    return _delete(db, user, MedicalCondition, item_id)


# --- Allergies --------------------------------------------------------------

@router.get("/allergies", response_model=list[AllergyOut])
def list_allergies(user: CurrentUser, db: DbSession) -> list[AllergyOut]:
    return [AllergyOut.model_validate(a) for a in _list(db, user, MedicalAllergy)]


@router.post("/allergies", response_model=AllergyOut, status_code=status.HTTP_201_CREATED)
def create_allergy(body: AllergyCreate, user: CurrentUser, db: DbSession) -> AllergyOut:
    return AllergyOut.model_validate(_create(db, user, MedicalAllergy, body))


@router.get("/allergies/{item_id}", response_model=AllergyOut)
def read_allergy(item_id: uuid.UUID, user: CurrentUser, db: DbSession) -> AllergyOut:
    return AllergyOut.model_validate(_get_owned(db, user, MedicalAllergy, item_id))


@router.patch("/allergies/{item_id}", response_model=AllergyOut)
def update_allergy(item_id: uuid.UUID, body: AllergyUpdate, user: CurrentUser, db: DbSession) -> AllergyOut:
    return AllergyOut.model_validate(_update(db, user, MedicalAllergy, item_id, body))


@router.delete("/allergies/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_allergy(item_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    return _delete(db, user, MedicalAllergy, item_id)


# --- Procedures -------------------------------------------------------------

@router.get("/procedures", response_model=list[ProcedureOut])
def list_procedures(user: CurrentUser, db: DbSession) -> list[ProcedureOut]:
    return [ProcedureOut.model_validate(p) for p in _list(db, user, MedicalProcedure)]


@router.post("/procedures", response_model=ProcedureOut, status_code=status.HTTP_201_CREATED)
def create_procedure(body: ProcedureCreate, user: CurrentUser, db: DbSession) -> ProcedureOut:
    return ProcedureOut.model_validate(_create(db, user, MedicalProcedure, body))


@router.get("/procedures/{item_id}", response_model=ProcedureOut)
def read_procedure(item_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ProcedureOut:
    return ProcedureOut.model_validate(_get_owned(db, user, MedicalProcedure, item_id))


@router.patch("/procedures/{item_id}", response_model=ProcedureOut)
def update_procedure(item_id: uuid.UUID, body: ProcedureUpdate, user: CurrentUser, db: DbSession) -> ProcedureOut:
    return ProcedureOut.model_validate(_update(db, user, MedicalProcedure, item_id, body))


@router.delete("/procedures/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_procedure(item_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    return _delete(db, user, MedicalProcedure, item_id)


# --- Additional notes -------------------------------------------------------

@router.get("/notes", response_model=NotesOut)
def read_notes(user: CurrentUser, db: DbSession) -> NotesOut:
    return _notes_out(_get_notes(db, user))


@router.put("/notes", response_model=NotesOut)
def replace_notes(body: NotesIn, user: CurrentUser, db: DbSession) -> NotesOut:
    row = _get_notes(db, user)
    if body.notes is None:
        if row is not None:
            db.delete(row)
            db.commit()
        return _notes_out(None)
    if row is None:
        row = MedicalNotes(user_id=user.id, notes=body.notes)
        db.add(row)
    else:
        row.notes = body.notes
        row.updated_at = func.now()
    try:
        db.commit()
    except IntegrityError:  # the same user's notes created twice at once
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="The notes were just changed. Please try again.") from None
    db.refresh(row)
    return _notes_out(row)
