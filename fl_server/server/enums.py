"""Local enum definitions for the FL server and hospital nodes — decoupled from the backend package.

These values mirror backend.app.models.enums and must stay in sync whenever the
canonical backend enums change.  Keeping them local means the fl_server and
hospital_nodes containers can start without the backend package installed.
"""

from enum import Enum


class AggregationStrategy(str, Enum):
    FEDAVG = "fedavg"
    WEIGHTED_FEDAVG = "weighted_fedavg"


class DatasetType(str, Enum):
    HEART_DISEASE = "heart_disease"
    DIABETES = "diabetes"
    BREAST_CANCER = "breast_cancer"


class ModelSource(str, Enum):
    FEDERATED = "federated"
    CENTRALIZED = "centralized"


class ModelFramework(str, Enum):
    PYTORCH = "pytorch"
    SCIKIT_LEARN = "scikit_learn"
    XGBOOST = "xgboost"

