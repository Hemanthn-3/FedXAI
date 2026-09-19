"""Global model lookup, checksum verification, and artifact loading."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import AppError, NotFoundError
from backend.app.models.enums import DatasetType, ModelSource
from backend.app.models.global_model import GlobalModel
from fl_server.server.dataset import schema_for
from fl_server.server.model import create_model

COMPACT_CLINICAL_FEATURES = ("age", "bp", "cholesterol", "glucose")


@dataclass(frozen=True)
class LoadedModelArtifact:
    version: str
    dataset_type: DatasetType
    input_dim: int
    feature_names: tuple[str, ...]
    preprocessing: dict[str, Any]
    metrics: dict[str, Any]
    state_dict: dict[str, Any]
    warnings: tuple[str, ...] = ()


class ModelService:
    """Resolve active models and load trusted model artifacts."""

    @staticmethod
    async def get_by_id(session: AsyncSession, model_id) -> GlobalModel | None:
        return await session.get(GlobalModel, model_id)

    @staticmethod
    async def get_active_model(
        session: AsyncSession,
        *,
        dataset_type: DatasetType,
        source: ModelSource,
    ) -> GlobalModel:
        result = await session.execute(
            select(GlobalModel).where(
                GlobalModel.dataset_type == dataset_type,
                GlobalModel.source == source,
                GlobalModel.is_active.is_(True),
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Active {source.value} model for {dataset_type.value}")
        return model

    @staticmethod
    def checksum_sha256(path: str | Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def verify_checksum(cls, *, path: str | Path, expected_sha256: str) -> None:
        actual = cls.checksum_sha256(path)
        if actual != expected_sha256:
            raise AppError(
                "Model artifact checksum verification failed",
                status_code=500,
                code="model_checksum_mismatch",
                details={"expected": expected_sha256, "actual": actual},
            )

    @staticmethod
    def _resolve_feature_names(
        *,
        artifact: dict[str, Any],
        dataset_type: DatasetType,
        input_dim: int,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        warnings: list[str] = []
        raw_feature_names = artifact.get("feature_names")
        if raw_feature_names:
            feature_names = tuple(str(name).strip().lower() for name in raw_feature_names)
            if len(feature_names) != input_dim:
                raise AppError(
                    "Model artifact feature metadata does not match input dimension",
                    status_code=500,
                    code="invalid_model_artifact",
                )
            return feature_names, tuple(warnings)

        schema = schema_for(dataset_type)
        if schema.input_dim == input_dim:
            warnings.append(
                "Model artifact did not include feature_names; inferred dataset schema order."
            )
            return schema.features, tuple(warnings)
        if input_dim == len(COMPACT_CLINICAL_FEATURES):
            warnings.append(
                "Model artifact did not include feature_names; inferred compact clinical order."
            )
            return COMPACT_CLINICAL_FEATURES, tuple(warnings)
        raise AppError(
            "Model artifact is missing feature metadata and cannot be used safely",
            status_code=500,
            code="invalid_model_artifact",
        )

    @classmethod
    def load_artifact(
        cls,
        *,
        path: str | Path,
        dataset_type: DatasetType,
        expected_sha256: str | None = None,
    ) -> LoadedModelArtifact:
        artifact_path = Path(path)
        if not artifact_path.exists():
            raise NotFoundError("Model artifact")
        if expected_sha256 is not None:
            cls.verify_checksum(path=artifact_path, expected_sha256=expected_sha256)

        payload = torch.load(artifact_path, map_location="cpu", weights_only=False)
        if not isinstance(payload, dict) or "state_dict" not in payload:
            raise AppError(
                "Model artifact has an unsupported format",
                status_code=500,
                code="invalid_model_artifact",
            )
        input_dim = int(payload.get("input_dim", 0))
        if input_dim <= 0:
            raise AppError(
                "Model artifact is missing input_dim",
                status_code=500,
                code="invalid_model_artifact",
            )
        feature_names, warnings = cls._resolve_feature_names(
            artifact=payload,
            dataset_type=dataset_type,
            input_dim=input_dim,
        )
        preprocessing = payload.get("preprocessing") or {
            "type": "identity",
            "means": [0.0] * input_dim,
            "scales": [1.0] * input_dim,
        }
        if "preprocessing" not in payload:
            warnings = (
                *warnings,
                "Model artifact did not include preprocessing metadata; identity transform used.",
            )
        model = create_model(input_dim)
        model.load_state_dict(payload["state_dict"], strict=True)
        return LoadedModelArtifact(
            version=str(payload.get("version", artifact_path.stem)),
            dataset_type=dataset_type,
            input_dim=input_dim,
            feature_names=feature_names,
            preprocessing=preprocessing,
            metrics=dict(payload.get("metrics") or {}),
            state_dict=model.state_dict(),
            warnings=warnings,
        )
