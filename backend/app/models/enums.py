"""Stable database enum values used across domain models."""

from enum import Enum


class UserRole(str, Enum):
    DOCTOR = "doctor"
    HOSPITAL_ADMIN = "hospital_admin"
    SYSTEM_ADMIN = "system_admin"
    RESEARCHER = "researcher"


class HospitalStatus(str, Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    TRAINING = "training"
    ERROR = "error"


class DatasetType(str, Enum):
    HEART_DISEASE = "heart_disease"
    DIABETES = "diabetes"
    BREAST_CANCER = "breast_cancer"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class TrainingRoundStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AggregationStrategy(str, Enum):
    FEDAVG = "fedavg"
    WEIGHTED_FEDAVG = "weighted_fedavg"


class ModelFramework(str, Enum):
    PYTORCH = "pytorch"
    SCIKIT_LEARN = "scikit_learn"
    XGBOOST = "xgboost"


class ModelSource(str, Enum):
    FEDERATED = "federated"
    CENTRALIZED = "centralized"


class XAIStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


def enum_values(enum_class: type[Enum]) -> list[str]:
    """Persist enum values rather than Python member names."""

    return [str(member.value) for member in enum_class]
