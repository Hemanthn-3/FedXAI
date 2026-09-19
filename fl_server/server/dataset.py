"""Healthcare dataset schema validation and local preprocessing for FL clients."""

from dataclasses import dataclass
from pathlib import Path

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


@dataclass(frozen=True)
class FederatedDataset:
    """Preprocessed local train/test arrays for one hospital node."""

    x_train: np.ndarray
    x_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    feature_names: tuple[str, ...]
    dataset_type: DatasetType
    scaler: StandardScaler
    imputer: SimpleImputer

    @property
    def input_dim(self) -> int:
        return self.x_train.shape[1]

    @property
    def train_examples(self) -> int:
        return int(self.x_train.shape[0])

    @property
    def test_examples(self) -> int:
        return int(self.x_test.shape[0])


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
    x_train = imputer.fit_transform(x_train).astype(np.float32)
    x_test = imputer.transform(x_test).astype(np.float32)
    x_train = scaler.fit_transform(x_train).astype(np.float32)
    x_test = scaler.transform(x_test).astype(np.float32)

    return FederatedDataset(
        x_train=x_train,
        x_test=x_test,
        y_train=y_train.astype(np.float32),
        y_test=y_test.astype(np.float32),
        feature_names=schema.features,
        dataset_type=schema.dataset_type,
        scaler=scaler,
        imputer=imputer,
    )
