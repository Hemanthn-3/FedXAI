"""Global model artifact registry for federated training rounds."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch

from fl_server.server.dataset import schema_for
from fl_server.server.enums import DatasetType, ModelSource
from fl_server.server.model import create_model, set_model_parameters


@dataclass(frozen=True)
class ModelArtifact:
    version: str
    path: Path
    checksum_sha256: str
    dataset_type: DatasetType
    round_number: int
    metrics: dict[str, Any]


class ModelRegistry:
    """Persist checksummed global model artifacts on local or mounted storage."""

    def __init__(self, artifact_root: str | Path) -> None:
        self.artifact_root = Path(artifact_root)

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def build_version(
        *,
        dataset_type: DatasetType,
        round_number: int,
        source: ModelSource = ModelSource.FEDERATED,
    ) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        return f"{source.value}-{dataset_type.value}-r{round_number:04d}-{timestamp}"

    def save_global_model(
        self,
        *,
        parameters: list[np.ndarray],
        input_dim: int,
        dataset_type: DatasetType,
        round_number: int,
        metrics: dict[str, Any],
        feature_names: tuple[str, ...] | list[str] | None = None,
        preprocessing: dict[str, Any] | None = None,
    ) -> ModelArtifact:
        """Save the aggregated model as a PyTorch state dictionary."""

        model = create_model(input_dim)
        set_model_parameters(model, parameters)
        resolved_feature_names = tuple(feature_names or schema_for(dataset_type).features)
        if len(resolved_feature_names) != input_dim:
            raise ValueError("feature_names length must match input_dim")
        resolved_preprocessing = preprocessing or {
            "type": "identity",
            "means": [0.0] * input_dim,
            "scales": [1.0] * input_dim,
        }
        version = self.build_version(dataset_type=dataset_type, round_number=round_number)
        target_dir = self.artifact_root / dataset_type.value
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{version}.pt"
        torch.save(
            {
                "version": version,
                "dataset_type": dataset_type.value,
                "round_number": round_number,
                "input_dim": input_dim,
                "feature_names": list(resolved_feature_names),
                "preprocessing": resolved_preprocessing,
                "metrics": metrics,
                "state_dict": model.state_dict(),
            },
            path,
        )
        return ModelArtifact(
            version=version,
            path=path,
            checksum_sha256=self._checksum(path),
            dataset_type=dataset_type,
            round_number=round_number,
            metrics=metrics,
        )

    def record_round_metrics(
        self,
        *,
        round_number: int,
        dataset_type: DatasetType,
        aggregation_strategy: str,
        metrics: dict[str, Any],
        artifact: ModelArtifact | None,
    ) -> Path:
        """Append one durable JSONL record for server-side monitoring."""

        self.artifact_root.mkdir(parents=True, exist_ok=True)
        history_path = self.artifact_root / "training_rounds.jsonl"
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "round_number": round_number,
            "dataset_type": dataset_type.value,
            "aggregation_strategy": aggregation_strategy,
            "metrics": metrics,
            "artifact": None
            if artifact is None
            else {
                "version": artifact.version,
                "path": str(artifact.path),
                "checksum_sha256": artifact.checksum_sha256,
            },
        }
        with history_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, sort_keys=True) + "\n")
        return history_path
