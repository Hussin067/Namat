"""Headache episodes: create, list, read, update and delete.

Every query is filtered by the authenticated user's id. Another user's episode
answers 404 (not 403), so its existence isn't revealed.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentUser, DbSession
from app.models import EpisodeSymptom, HeadacheEpisode, MedicationDose, Symptom, User
from app.schemas.episode import (
    EpisodeCreate,
    EpisodeList,
    EpisodeOut,
    EpisodeUpdate,
    MedicationIn,
    MedicationOut,
    SymptomOut,
)

router = APIRouter(prefix="/episodes", tags=["episodes"])

LOAD_DETAILS = (
    selectinload(HeadacheEpisode.symptom_links).selectinload(EpisodeSymptom.symptom),
    selectinload(HeadacheEpisode.medication_doses),
)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Episode not found.")


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _to_out(episode: HeadacheEpisode) -> EpisodeOut:
    return EpisodeOut(
        id=episode.id,
        started_at=episode.started_at,
        ended_at=episode.ended_at,
        peak_intensity=episode.peak_intensity,
        pain_location=episode.pain_location,
        had_aura=episode.had_aura,
        notes=episode.notes,
        symptoms=[
            SymptomOut.model_validate(link.symptom)
            for link in sorted(episode.symptom_links, key=lambda link: link.symptom_id)
        ],
        medications=[
            MedicationOut.model_validate(dose)
            for dose in sorted(episode.medication_doses, key=lambda dose: dose.taken_at)
        ],
        created_at=episode.created_at,
        updated_at=episode.updated_at,
    )


def _get_owned(db: Session, user: User, episode_id: uuid.UUID) -> HeadacheEpisode:
    episode = db.scalar(
        select(HeadacheEpisode)
        .where(HeadacheEpisode.id == episode_id, HeadacheEpisode.user_id == user.id)
        .options(*LOAD_DETAILS)
        .execution_options(populate_existing=True)  # always reflect the database
    )
    if episode is None:
        raise _not_found()
    return episode


def _check_symptoms_exist(db: Session, symptom_ids: list[int]) -> None:
    if not symptom_ids:
        return
    known = set(db.scalars(select(Symptom.id).where(Symptom.id.in_(symptom_ids))))
    unknown = sorted(set(symptom_ids) - known)
    if unknown:
        raise _invalid(f"Unknown symptom_ids: {unknown}")


def _set_symptoms(episode: HeadacheEpisode, symptom_ids: list[int]) -> None:
    """Make the episode's symptoms exactly `symptom_ids`, keeping unchanged links."""
    wanted = set(symptom_ids)
    for link in list(episode.symptom_links):
        if link.symptom_id not in wanted:
            episode.symptom_links.remove(link)  # delete-orphan removes the row
    existing = {link.symptom_id for link in episode.symptom_links}
    for symptom_id in symptom_ids:
        if symptom_id not in existing:
            episode.symptom_links.append(EpisodeSymptom(symptom_id=symptom_id))


def _add_medications(episode: HeadacheEpisode, user: User, medications: list[MedicationIn]) -> None:
    for med in medications:
        episode.medication_doses.append(
            MedicationDose(
                user_id=user.id,  # owner from the token; the composite FK ties it to the episode's owner
                medication_name=med.medication_name,
                dose_amount=med.dose_amount,
                dose_unit=med.dose_unit,
                taken_at=med.taken_at or episode.started_at,
                relief_rating=med.relief_rating,
            )
        )


def _delete_medications(db: Session, episode: HeadacheEpisode) -> None:
    for dose in list(episode.medication_doses):
        db.delete(dose)
    db.flush()
    db.expire(episode, ["medication_doses"])


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        # A database rule caught something the schema didn't (e.g. a race).
        db.rollback()
        raise _invalid("The episode data isn't valid.") from None


@router.get("", response_model=EpisodeList)
def list_episodes(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EpisodeList:
    """The current user's episodes, newest first."""
    total = db.scalar(select(func.count()).select_from(HeadacheEpisode).where(HeadacheEpisode.user_id == user.id))
    episodes = db.scalars(
        select(HeadacheEpisode)
        .where(HeadacheEpisode.user_id == user.id)
        .order_by(HeadacheEpisode.started_at.desc(), HeadacheEpisode.id.desc())
        .limit(limit)
        .offset(offset)
        .options(*LOAD_DETAILS)
    )
    return EpisodeList(items=[_to_out(e) for e in episodes], total=total, limit=limit, offset=offset)


@router.post("", response_model=EpisodeOut, status_code=status.HTTP_201_CREATED)
def create_episode(body: EpisodeCreate, user: CurrentUser, db: DbSession) -> EpisodeOut:
    _check_symptoms_exist(db, body.symptom_ids)
    episode = HeadacheEpisode(
        user_id=user.id,
        started_at=body.started_at,
        ended_at=body.ended_at,
        peak_intensity=body.peak_intensity,
        pain_location=body.pain_location,
        had_aura=body.had_aura,
        notes=body.notes,
    )
    db.add(episode)
    _set_symptoms(episode, body.symptom_ids)
    _add_medications(episode, user, body.medications)
    _commit(db)
    return _to_out(_get_owned(db, user, episode.id))


@router.get("/{episode_id}", response_model=EpisodeOut)
def read_episode(episode_id: uuid.UUID, user: CurrentUser, db: DbSession) -> EpisodeOut:
    return _to_out(_get_owned(db, user, episode_id))


@router.patch("/{episode_id}", response_model=EpisodeOut)
def update_episode(episode_id: uuid.UUID, body: EpisodeUpdate, user: CurrentUser, db: DbSession) -> EpisodeOut:
    episode = _get_owned(db, user, episode_id)
    changes = body.model_dump(exclude_unset=True, exclude={"symptom_ids", "medications"})

    started_at = changes.get("started_at", episode.started_at)
    ended_at = changes["ended_at"] if "ended_at" in changes else episode.ended_at
    if ended_at is not None and ended_at < started_at:
        raise _invalid("ended_at can't be earlier than started_at")

    for field, value in changes.items():
        setattr(episode, field, value)
    if "symptom_ids" in body.model_fields_set:
        _check_symptoms_exist(db, body.symptom_ids)
        _set_symptoms(episode, body.symptom_ids)
    if "medications" in body.model_fields_set:
        _delete_medications(db, episode)
        _add_medications(episode, user, body.medications)

    episode.updated_at = func.now()  # also counts symptom/medication-only edits
    _commit(db)
    return _to_out(_get_owned(db, user, episode.id))


@router.delete("/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_episode(episode_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    episode = _get_owned(db, user, episode_id)
    # Doses logged with this episode are part of it, so they go too. (The database
    # alone would keep them as unlinked doses, which the user could no longer see.)
    _delete_medications(db, episode)
    db.delete(episode)  # its symptom links are removed by ON DELETE CASCADE
    _commit(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
