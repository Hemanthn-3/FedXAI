"""Healthcare dataset schema validation and shared preprocessing for FL clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from fl_server.server.enums import DatasetType


@dataclass(frozen=True)
class DatasetSchema:
    dataset_type: DatasetType
    features: tuple[str, ...]
    target: str
    label_mapping: dict[str, int]

    @property
    def input_dim(self) -> int:
        return len(self.features)


DATASET_SCHEMAS: dict[DatasetType, DatasetSchema] = {
    DatasetType.HEART_DISEASE: DatasetSchema(
        dataset_type=DatasetType.HEART_DISEASE,
        features=("age", "sex", "cp", "trestbps", "chol", "fbs", "thalach", "exang", "oldpeak"),
        target="target",
        label_mapping={"0": 0, "1": 1},
    ),
    DatasetType.DIABETES: DatasetSchema(
        dataset_type=DatasetType.DIABETES,
        features=("pregnancies", "glucose", "bloodpressure", "insulin", "bmi", "age"),
        target="outcome",
        label_mapping={"0": 0, "1": 1},
    ),
    DatasetType.BREAST_CANCER: DatasetSchema(
        dataset_type=DatasetType.BREAST_CANCER,
        features=("radius", "texture", "perimeter", "area", "smoothness"),
        target="diagnosis",
        label_mapping={
            "0": 0,
            "1": 1,
            "b": 0,
            "benign": 0,
            "m": 1,
            "malignant": 1,
        },
    ),
}


@dataclass
class FederatedDataset:
    """Local train/test arrays for one hospital node.

    ``x_train_raw`` / ``x_test_raw`` hold the imputed-but-unscaled arrays so the
    shared preprocessing specification sent by the FL server can be re-applied
    idempotently each round.  On load, arrays are locally scaled (legacy
    behaviour for standalone runs); once the server sends a ``preprocessing``
    spec, the shared transform supersedes it.
    """

    x_train: np.ndarray
    x_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    feature_names: tuple[str, ...]
    dataset_type: DatasetType
    scaler: StandardScaler
    imputer: SimpleImputer
    x_train_raw: np.ndarray | None = None
    x_test_raw: np.ndarray | None = None
    applied_preprocessing: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def input_dim(self) -> int:
        return int(self.x_train.shape[1])

    @property
    def train_examples(self) -> int:
        return int(self.x_train.shape[0])

    @property
    def test_examples(self) -> int:
        return int(self.x_test.shape[0])

    def apply_preprocessing(self, spec: dict[str, Any] | None) -> None:
        """Apply a shared preprocessing spec to the raw arrays (idempotent)."""

        if spec is None or spec == self.applied_preprocessing:
            return
        if self.x_train_raw is None or self.x_test_raw is None:
            raise ValueError("FederatedDataset is missing raw arrays for preprocessing")
        self.x_train = apply_shared_preprocessing(self.x_train_raw, spec)
        self.x_test = apply_shared_preprocessing(self.x_test_raw, spec)
        self.applied_preprocessing = dict(spec)


def apply_shared_preprocessing(x: np.ndarray, spec: dict[str, Any] | None) -> np.ndarray:
    """Transform raw feature rows using the server-provided preprocessing spec.

    Supported types:
      * ``identity``      — no change
      * ``standardization`` — ``(x - means) / scales`` with per-feature arrays
    """

    if not spec:
        return x
    kind = str(spec.get("type", "identity")).lower()
    if kind == "identity":
        return x
    if kind == "standardization":
        means = np.asarray(spec.get("means", []), dtype=np.float32)
        scales = np.asarray(spec.get("scales", []), dtype=np.float32)
        if means.shape != scales.shape or means.ndim != 1:
            raise ValueError("preprocessing means/scales must be 1-D arrays of equal length")
        if means.shape[0] != x.shape[1]:
            raise ValueError(
                f"preprocessing expects {means.shape[0]} features, data has {x.shape[1]}"
            )
        safe_scales = np.where(scales == 0, 1.0, scales)
        return ((x - means) / safe_scales).astype(np.float32)
    raise ValueError(f"Unsupported preprocessing type: {kind}")


def schema_for(dataset_type: DatasetType | str) -> DatasetSchema:
    resolved = DatasetType(dataset_type)
    return DATASET_SCHEMAS[resolved]


def _encode_target(values: pd.Series, schema: DatasetSchema) -> pd.Series:
    normalized = values.astype(str).str.strip().str.lower()
    mapped = normalized.map(schema.label_mapping)
    if mapped.isna().any():
        bad_values = sorted(normalized[mapped.isna()].unique().tolist())
        raise ValueError(f"Unsupported labels for {schema.target}: {bad_values}")
    return mapped.astype("int64")


def validate_dataframe(df: pd.DataFrame, dataset_type: DatasetType | str) -> pd.DataFrame:
    """Validate required columns and coerce a healthcare dataframe for FL training."""

    schema = schema_for(dataset_type)
    required = set(schema.features + (schema.target,))
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns for {schema.dataset_type.value}: {missing}")

    clean = df.loc[:, list(schema.features) + [schema.target]].copy()
    for feature in schema.features:
        clean[feature] = pd.to_numeric(clean[feature], errors="coerce")
    clean[schema.target] = _encode_target(clean[schema.target], schema)
    clean = clean.dropna(subset=[schema.target]).drop_duplicates()
    if clean[schema.target].nunique() < 2:
        raise ValueError("Training data must contain both positive and negative classes")
    if len(clean) < 10:
        raise ValueError("Training data must contain at least 10 valid rows")
    return clean


def load_healthcare_csv(
    path: str | Path,
    *,
    dataset_type: DatasetType | str,
    test_size: float = 0.2,
    random_state: int = 42,
) -> FederatedDataset:
    """Load and preprocess one hospital-local CSV file.

    This function runs inside a hospital node. It returns arrays for local model
    training and never transmits raw rows to the FL server.
    """

    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Hospital dataset does not exist: {dataset_path}")

    schema = schema_for(dataset_type)
    clean = validate_dataframe(pd.read_csv(dataset_path), schema.dataset_type)
    x = clean.loc[:, schema.features].to_numpy(dtype=np.float32)
    y = clean.loc[:, schema.target].to_numpy(dtype=np.float32)
    stratify = y if len(np.unique(y)) > 1 else None
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )

    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    x_train_imp = imputer.fit_transform(x_train).astype(np.float32)
    x_test_imp = imputer.transform(x_test).astype(np.float32)
    # Legacy local scaling — superseded once the server sends a shared spec.
    x_train = scaler.fit_transform(x_train_imp).astype(np.float32)
    x_test = scaler.transform(x_test_imp).astype(np.float32)

    return FederatedDataset(
        x_train=x_train,
        x_test=x_test,
        y_train=y_train.astype(np.float32),
        y_test=y_test.astype(np.float32),
        feature_names=schema.features,
        dataset_type=schema.dataset_type,
        scaler=scaler,
        imputer=imputer,
        x_train_raw=x_train_imp,
        x_test_raw=x_test_imp,
    )
