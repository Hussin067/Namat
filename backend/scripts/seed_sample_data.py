"""Insert SYNTHETIC sample data into the local database, then read it back.

Run from backend/:
    python -m scripts.seed_sample_data

All people and values here are invented. Never put real patient data in this file.
Safe to re-run: previous sample users (and, by cascade, all their rows) are
deleted first.
"""

import random
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    DailyFactor,
    EpisodeSymptom,
    HeadacheEpisode,
    MedicationDose,
    SleepLog,
    Symptom,
    User,
)

# example.com is reserved for documentation, so these can never be real inboxes.
SAMPLE_EMAILS = ("sample.user1@example.com", "sample.user2@example.com")

# Not a real hash: no password can ever match it, so sample users can't log in.
# Real hashes are created by the auth task (Argon2/bcrypt).
FAKE_PASSWORD_HASH = "!synthetic-account-no-login"

DAYS = 14


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)


def delete_previous_sample_users(db: Session) -> None:
    users = db.scalars(select(User).where(func.lower(User.email).in_(SAMPLE_EMAILS)))
    for user in users:
        db.delete(user)  # ON DELETE CASCADE removes all of their rows
    db.flush()


def create_user(db: Session, email: str, name: str, rng: random.Random) -> User:
    symptoms = {s.name: s for s in db.scalars(select(Symptom))}
    user = User(email=email, password_hash=FAKE_PASSWORD_HASH, display_name=name)
    db.add(user)

    start = date.today() - timedelta(days=DAYS)
    for offset in range(DAYS):
        day = start + timedelta(days=offset)

        bedtime = at(day, 22, rng.choice([0, 30])) + timedelta(hours=rng.randint(0, 3))
        user.sleep_logs.append(
            SleepLog(
                sleep_date=day,
                bedtime=bedtime,
                wake_time=bedtime + timedelta(minutes=rng.randint(300, 540)),
                quality=rng.randint(1, 5),
                awakenings=rng.randint(0, 4),
            )
        )
        user.daily_factors.append(
            DailyFactor(
                log_date=day,
                stress_level=rng.randint(0, 10),
                caffeine_mg=rng.choice([0, 80, 160, 240, 320]),
                water_ml=rng.randint(4, 12) * 250,
                alcohol_units=Decimal("0"),
                exercise_minutes=rng.choice([0, 0, 20, 30, 45]),
                skipped_meal=rng.random() < 0.2,
            )
        )

        # Roughly one episode every four days.
        if rng.random() < 0.25:
            started = at(day, rng.randint(7, 18))
            episode = HeadacheEpisode(
                started_at=started,
                ended_at=started + timedelta(hours=rng.randint(2, 20)),
                peak_intensity=rng.randint(4, 9),
                pain_location=rng.choice(["left", "right", "bilateral", "frontal"]),
                had_aura=rng.random() < 0.3,
                notes="Synthetic sample episode.",
            )
            for symptom_name in rng.sample(sorted(symptoms), k=3):
                episode.symptom_links.append(
                    EpisodeSymptom(
                        symptom=symptoms[symptom_name], severity=rng.randint(1, 3)
                    )
                )
            user.episodes.append(episode)
            user.medication_doses.append(
                MedicationDose(
                    episode=episode,
                    medication_name="Sample pain reliever",
                    dose_amount=Decimal("500"),
                    dose_unit="mg",
                    taken_at=started + timedelta(minutes=45),
                    relief_rating=rng.randint(0, 3),
                )
            )

    # One preventive dose that isn't linked to any episode.
    user.medication_doses.append(
        MedicationDose(
            medication_name="Sample preventive",
            dose_amount=Decimal("10"),
            dose_unit="mg",
            taken_at=at(start, 8),
        )
    )
    return user


def print_summary(db: Session) -> None:
    users = db.scalars(
        select(User)
        .where(func.lower(User.email).in_(SAMPLE_EMAILS))
        .order_by(User.email)
        .options(
            selectinload(User.episodes)
            .selectinload(HeadacheEpisode.symptom_links)
            .selectinload(EpisodeSymptom.symptom),
            selectinload(User.episodes).selectinload(HeadacheEpisode.medication_doses),
            selectinload(User.medication_doses),
            selectinload(User.sleep_logs),
            selectinload(User.daily_factors),
        )
    )
    for user in users:
        avg_sleep = sum(s.duration_minutes for s in user.sleep_logs) / len(user.sleep_logs)
        print(f"\n{user!r}  ({user.display_name})")
        print(
            f"  episodes={len(user.episodes)}  doses={len(user.medication_doses)}  "
            f"sleep_logs={len(user.sleep_logs)}  daily_factors={len(user.daily_factors)}  "
            f"avg_sleep={avg_sleep / 60:.1f}h"
        )
        for ep in sorted(user.episodes, key=lambda e: e.started_at, reverse=True)[:3]:
            symptoms = ", ".join(link.symptom.name for link in ep.symptom_links)
            meds = ", ".join(
                f"{d.medication_name} {d.dose_amount}{d.dose_unit}" for d in ep.medication_doses
            )
            print(
                f"  - {ep.started_at:%Y-%m-%d %H:%M} intensity={ep.peak_intensity} "
                f"{ep.pain_location} | {symptoms} | {meds}"
            )


def main() -> None:
    if get_settings().app_env != "development":
        raise SystemExit("Refusing to seed: APP_ENV is not 'development'.")

    rng = random.Random(42)  # fixed seed: same sample data on every run
    with SessionLocal() as db:
        delete_previous_sample_users(db)
        create_user(db, SAMPLE_EMAILS[0], "Sample User One", rng)
        create_user(db, SAMPLE_EMAILS[1], "Sample User Two", rng)
        db.commit()
        print("Saved synthetic sample data. Reading it back from PostgreSQL...")

    # A brand-new session proves the data comes from the database, not memory.
    with SessionLocal() as db:
        print_summary(db)


if __name__ == "__main__":
    main()
