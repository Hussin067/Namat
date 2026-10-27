"""The shared symptom catalog (seeded by the initial migration)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import DbSession, get_current_user
from app.models import Symptom
from app.schemas.episode import SymptomOut

router = APIRouter(prefix="/symptoms", tags=["symptoms"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[SymptomOut])
def list_symptoms(db: DbSession) -> list[Symptom]:
    return list(db.scalars(select(Symptom).order_by(Symptom.id)))
