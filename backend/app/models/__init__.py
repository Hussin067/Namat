"""Import every model here so Base.metadata knows all tables (Alembic relies on this)."""

from app.models.daily_factor import DailyFactor
from app.models.episode import EpisodeSymptom, HeadacheEpisode, Symptom
from app.models.medical_history import MedicalAllergy, MedicalCondition, MedicalNotes, MedicalProcedure
from app.models.medication import MedicationDose
from app.models.sleep import SleepLog
from app.models.user import User

__all__ = [
    "DailyFactor",
    "EpisodeSymptom",
    "HeadacheEpisode",
    "MedicalAllergy",
    "MedicalCondition",
    "MedicalNotes",
    "MedicalProcedure",
    "MedicationDose",
    "SleepLog",
    "Symptom",
    "User",
]
