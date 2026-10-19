"""Check that the database itself enforces the schema's rules.

Run from backend/:
    python -m scripts.verify_database

Everything runs inside one transaction that is rolled back at the end,
so the database is left exactly as it was. Uses synthetic data only.
"""

import sys
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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

NOW = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
results: list[bool] = []


def report(ok: bool, label: str, detail: str = "") -> None:
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))


def expect_rejected(db: Session, label: str, action: Callable[[], None]) -> None:
    """The action must be refused by PostgreSQL; the savepoint undoes it either way."""
    savepoint = db.begin_nested()
    try:
        action()
        db.flush()
    except IntegrityError as exc:
        savepoint.rollback()
        report(True, label, f"rejected by {exc.orig.diag.constraint_name}")
    else:
        savepoint.rollback()
        report(False, label, "was accepted but should have been rejected")


def new_user(db: Session, email: str) -> User:
    user = User(email=email, password_hash="!synthetic-account-no-login")
    db.add(user)
    db.flush()
    return user


def main() -> None:
    with SessionLocal() as db:
        alice = new_user(db, "verify.a@example.com")
        bob = new_user(db, "verify.b@example.com")
        episode = HeadacheEpisode(user=alice, started_at=NOW, peak_intensity=6)
        db.add(episode)
        db.flush()

        print("Data rules")
        expect_rejected(db, "intensity above 10", lambda: db.add(
            HeadacheEpisode(user=alice, started_at=NOW, peak_intensity=11)))
        expect_rejected(db, "episode ending before it starts", lambda: db.add(
            HeadacheEpisode(user=alice, started_at=NOW, ended_at=NOW - timedelta(hours=1))))
        expect_rejected(db, "unknown pain location", lambda: db.add(
            HeadacheEpisode(user=alice, started_at=NOW, pain_location="elbow")))
        expect_rejected(db, "negative caffeine", lambda: db.add(
            DailyFactor(user=alice, log_date=date(2026, 1, 15), caffeine_mg=-5)))
        expect_rejected(db, "wake time before bedtime", lambda: db.add(
            SleepLog(user=alice, sleep_date=date(2026, 1, 14), bedtime=NOW, wake_time=NOW - timedelta(hours=2))))

        print("\nUniqueness")
        expect_rejected(db, "same email with different letter case", lambda: db.add(
            User(email="VERIFY.A@example.com", password_hash="!synthetic-account-no-login")))

        def two_sleep_logs_same_night() -> None:
            for _ in range(2):
                db.add(SleepLog(user=alice, sleep_date=date(2026, 1, 10),
                                bedtime=NOW, wake_time=NOW + timedelta(hours=7)))
        expect_rejected(db, "two sleep logs for the same night", two_sleep_logs_same_night)

        symptom = db.scalars(select(Symptom).order_by(Symptom.id)).first()

        def same_symptom_twice() -> None:
            db.add(EpisodeSymptom(episode=episode, symptom=symptom))
            db.flush()
            db.add(EpisodeSymptom(episode_id=episode.id, symptom_id=symptom.id))
        expect_rejected(db, "same symptom twice on one episode", same_symptom_twice)

        print("\nUser data isolation")
        expect_rejected(db, "Bob's dose pointing at Alice's episode", lambda: db.add(
            MedicationDose(user_id=bob.id, episode_id=episode.id,
                           medication_name="Sample", taken_at=NOW)))

        print("\nDelete behaviour")
        db.add(EpisodeSymptom(episode=episode, symptom=symptom))
        dose = MedicationDose(user=alice, episode=episode, medication_name="Sample", taken_at=NOW)
        db.add(dose)
        db.flush()
        expect_rejected(db, "deleting a symptom that is in use", lambda: db.execute(
            delete(Symptom).where(Symptom.id == symptom.id)))

        db.execute(delete(HeadacheEpisode).where(HeadacheEpisode.id == episode.id))
        db.expire_all()
        dose = db.get(MedicationDose, dose.id)
        report(dose is not None and dose.episode_id is None and dose.user_id == alice.id,
               "deleting an episode keeps the dose, unlinks it, keeps its owner")

        db.execute(delete(User).where(User.id == alice.id))
        leftovers = sum(
            db.scalar(select(func.count()).select_from(model).where(model.user_id == alice.id))
            for model in (HeadacheEpisode, MedicationDose, SleepLog, DailyFactor)
        )
        report(leftovers == 0, "deleting a user removes all of their rows", f"{leftovers} left")

        db.rollback()  # leave the database untouched

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed; all test rows rolled back.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
