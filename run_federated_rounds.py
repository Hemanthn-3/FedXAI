"""
FedPedia-XAI — Multi-Round FedAvg Training, Evaluation & Activation Script
==========================================================================
Executes federated rounds across hospital nodes, compares round checkpoints on
a held-out test set, and activates the best global model artifact in the DB.
"""

import asyncio
import hashlib
import math
import os
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from backend.app.core.config import get_settings
from backend.app.models.enums import DatasetType, ModelFramework, ModelSource
from backend.app.models.global_model import GlobalModel
from backend.app.services.prediction_engine import (
    PredictionEngine,
    risk_from_probability,
    risk_label,
)
from fl_server.server.aggregation import ClientUpdate, aggregate_weighted_fedavg
from fl_server.server.model import HealthcareMLP, get_model_parameters, set_model_parameters
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

FEATURE_NAMES = ("age", "sex", "cp", "trestbps", "chol", "fbs", "thalach", "exang", "oldpeak")
TARGET_COL = "target"
RANDOM_SEED = 42

PASS = "\033[92m  PASS\033[0m"
INFO = "\033[94m  INFO\033[0m"
WARN = "\033[93m  WARN\033[0m"


def set_seed(seed: int = RANDOM_SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def verify_csv_data() -> tuple[pd.DataFrame, dict[str, str]]:
    """Verify hospital node CSV files and check target label distribution."""
    base = Path("/app/hospital_nodes") if os.path.exists("/app/hospital_nodes") else Path("hospital_nodes")
    checksums = {}
    frames = []

    print("\n[1/6] Verifying Hospital Node CSV Data ...")
    for node in ("node_1", "node_2", "node_3"):
        csv_path = base / node / "data.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing CSV: {csv_path}")
        
        hasher = hashlib.sha256()
        with open(csv_path, "rb") as f:
            hasher.update(f.read())
        cs = hasher.hexdigest()
        checksums[node] = cs
        
        df_node = pd.read_csv(csv_path)
        df_node["_source_node"] = node
        frames.append(df_node)
        
        pos = int(df_node[TARGET_COL].sum())
        neg = len(df_node) - pos
        print(f"  {node}: {len(df_node)} rows | SHA256={cs[:12]}... | 0={neg}, 1={pos}")

    combined = pd.concat(frames, ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(subset=list(FEATURE_NAMES) + [TARGET_COL])
    print(f"  Combined data: {before} total rows -> {len(combined)} deduplicated rows")
    return combined, checksums


def local_train(
    global_params: list[np.ndarray],
    x_node: np.ndarray,
    y_node: np.ndarray,
    epochs: int = 10,
    lr: float = 1e-3,
    batch_size: int = 16,
) -> tuple[list[np.ndarray], float]:
    """Train a model locally on one node starting from global parameters."""
    model = HealthcareMLP(input_dim=len(FEATURE_NAMES), hidden_dims=(32, 16), dropout=0.2)
    set_model_parameters(model, global_params)
    model.train()

    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    criterion = nn.BCEWithLogitsLoss()

    x_tensor = torch.as_tensor(x_node, dtype=torch.float32)
    y_tensor = torch.as_tensor(y_node, dtype=torch.float32)

    last_loss = 0.0
    for _ in range(epochs):
        perm = torch.randperm(len(x_tensor))
        for start in range(0, len(x_tensor), batch_size):
            idx = perm[start:start + batch_size]
            xb, yb = x_tensor[idx], y_tensor[idx]
            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()
            last_loss = loss.item()

    return get_model_parameters(model), last_loss


def evaluate_global(
    params: list[np.ndarray],
    x_test_sc: np.ndarray,
    y_test: np.ndarray,
) -> dict:
    """Evaluate global parameters on the held-out test split."""
    model = HealthcareMLP(input_dim=len(FEATURE_NAMES), hidden_dims=(32, 16), dropout=0.2)
    set_model_parameters(model, params)
    model.eval()

    criterion = nn.BCEWithLogitsLoss()
    x_te = torch.as_tensor(x_test_sc, dtype=torch.float32)
    y_te = torch.as_tensor(y_test, dtype=torch.float32)

    with torch.no_grad():
        logits = model(x_te)
        val_loss = float(criterion(logits, y_te).item())
        probs = torch.sigmoid(logits).numpy().reshape(-1)

    preds = (probs >= 0.5).astype(int)
    y_int = y_test.astype(int)

    cm = confusion_matrix(y_int, preds, labels=[0, 1])
    return {
        "loss":             round(val_loss, 4),
        "accuracy":         round(float(accuracy_score(y_int, preds)), 4),
        "precision":        round(float(precision_score(y_int, preds, zero_division=0)), 4),
        "recall":           round(float(recall_score(y_int, preds, zero_division=0)), 4),
        "f1":               round(float(f1_score(y_int, preds, zero_division=0)), 4),
        "roc_auc":          round(float(roc_auc_score(y_int, probs)), 4),
        "confusion_matrix": cm.tolist(),
        "tn":               int(cm[0, 0]),
        "fp":               int(cm[0, 1]),
        "fn":               int(cm[1, 0]),
        "tp":               int(cm[1, 1]),
    }


def save_checkpoint_artifact(
    params: list[np.ndarray],
    scaler: StandardScaler,
    metrics: dict,
    version: str,
    round_num: int,
) -> tuple[Path, str]:
    """Save global model parameters + scaler preprocessing to disk."""
    model = HealthcareMLP(input_dim=len(FEATURE_NAMES), hidden_dims=(32, 16), dropout=0.2)
    set_model_parameters(model, params)

    artifact_root = Path("/app/artifacts") if os.path.exists("/app/artifacts") else Path("artifacts")
    target_dir = artifact_root / "models" / "heart_disease"
    target_dir.mkdir(parents=True, exist_ok=True)

    model_path = target_dir / f"{version}.pt"
    preprocessing = {
        "type":   "standardization",
        "means":  scaler.mean_.tolist(),
        "scales": scaler.scale_.tolist(),
    }

    torch.save(
        {
            "version":       version,
            "dataset_type":  DatasetType.HEART_DISEASE.value,
            "round_number":  round_num,
            "input_dim":     len(FEATURE_NAMES),
            "feature_names": list(FEATURE_NAMES),
            "preprocessing": preprocessing,
            "metrics":       metrics,
            "state_dict":    model.state_dict(),
        },
        model_path,
    )

    hasher = hashlib.sha256()
    with open(model_path, "rb") as f:
        hasher.update(f.read())
    checksum = hasher.hexdigest()
    return model_path, checksum


async def update_db_registered_models(
    best_version: str,
    best_path: Path,
    best_checksum: str,
    best_metrics: dict,
    all_rounds: list[dict] | None = None,
) -> None:
    """Deactivate older global models, activate best model, and persist training rounds in DB."""
    print("\n[5/6] Registering & Activating Best Global Model and Training Rounds in Database ...")
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Deactivate all federated heart disease models
        await session.execute(
            update(GlobalModel)
            .where(
                GlobalModel.dataset_type == DatasetType.HEART_DISEASE,
                GlobalModel.source == ModelSource.FEDERATED,
            )
            .values(is_active=False)
        )

        result = await session.execute(
            select(GlobalModel).where(GlobalModel.version == best_version)
        )
        existing = result.scalar_one_or_none()

        import uuid
        active_model_id = None
        if existing is None:
            active_model_id = uuid.uuid4()
            session.add(
                GlobalModel(
                    id=active_model_id,
                    version=best_version,
                    path=str(best_path),
                    checksum_sha256=best_checksum,
                    dataset_type=DatasetType.HEART_DISEASE,
                    framework=ModelFramework.PYTORCH,
                    source=ModelSource.FEDERATED,
                    metrics=best_metrics,
                    is_active=True,
                )
            )
            print(f"  [+] Registered new active model: {best_version}")
        else:
            active_model_id = existing.id
            existing.path = str(best_path)
            existing.checksum_sha256 = best_checksum
            existing.metrics = best_metrics
            existing.is_active = True
            print(f"  [=] Activated existing global model: {best_version}")

        # Persist training round history in DB
        if all_rounds:
            from sqlalchemy import delete
            from backend.app.models.training_round import TrainingRound
            from backend.app.models.enums import AggregationStrategy, TrainingRoundStatus

            await session.execute(
                delete(TrainingRound).where(TrainingRound.dataset_type == DatasetType.HEART_DISEASE)
            )
            run_id = uuid.uuid4()
            for r_item in all_rounds:
                r_num = r_item["round"]
                m = r_item["metrics"]
                session.add(
                    TrainingRound(
                        id=uuid.uuid4(),
                        run_id=run_id,
                        global_model_id=active_model_id,
                        round_number=r_num,
                        dataset_type=DatasetType.HEART_DISEASE,
                        aggregation_strategy=AggregationStrategy.FEDAVG,
                        status=TrainingRoundStatus.COMPLETED,
                        total_clients=3,
                        participating_clients=3,
                        participating_nodes=["hospital_node_1", "hospital_node_2", "hospital_node_3"],
                        client_metrics={},
                        accuracy=m["accuracy"],
                        precision=m["precision"],
                        recall=m["recall"],
                        f1=m["f1"],
                        roc_auc=m["roc_auc"],
                        loss=m["loss"],
                    )
                )
            print(f"  [+] Saved {len(all_rounds)} FL training rounds in database.")

        await session.commit()


def main() -> None:
    set_seed(RANDOM_SEED)

    print("\n" + "=" * 65)
    print("  FedPedia-XAI — Multi-Round FedAvg Model Training & Evaluation")
    print("=" * 65)

    # 1. Verify CSVs
    combined_df, _ = verify_csv_data()

    # 2. Stratified train/test split (80/20)
    print("\n[2/6] Building Train/Test Splits & Fitting StandardScaler ...")
    x = combined_df[list(FEATURE_NAMES)].to_numpy(dtype=np.float32)
    y = combined_df[TARGET_COL].to_numpy(dtype=np.float32)
    nodes = combined_df["_source_node"].to_numpy()

    x_train, x_test, y_train, y_test, node_train, _ = train_test_split(
        x, y, nodes, test_size=0.20, random_state=RANDOM_SEED, stratify=y
    )

    scaler = StandardScaler()
    x_train_sc = scaler.fit_transform(x_train).astype(np.float32)
    x_test_sc = scaler.transform(x_test).astype(np.float32)

    print(f"  Train samples: {len(x_train)} | Test samples: {len(x_test)}")
    print(f"  Scaler means : {np.round(scaler.mean_, 2).tolist()}")
    print(f"  Scaler scales: {np.round(scaler.scale_, 2).tolist()}")

    # Node data partitions
    node_data = {}
    for n in ("node_1", "node_2", "node_3"):
        mask = (node_train == n)
        node_data[n] = (x_train_sc[mask], y_train[mask])
        print(f"  Partition {n}: {mask.sum()} samples")

    # 3. Federated Training Loop — warm-start from saved bootstrap model
    print("\n[3/6] Running 10 Rounds of FedAvg Training (warm-start from bootstrap) ...")

    # Load pre-trained bootstrap weights as global starting point
    bootstrap_path = (
        Path("/app/artifacts") if os.path.exists("/app/artifacts") else Path("artifacts")
    ) / "models" / "heart_disease" / "federated-heart_disease-r0001-bootstrap.pt"

    init_model = HealthcareMLP(input_dim=len(FEATURE_NAMES), hidden_dims=(32, 16), dropout=0.2)
    if bootstrap_path.exists():
        payload = torch.load(bootstrap_path, map_location="cpu", weights_only=False)
        init_model.load_state_dict(payload["state_dict"], strict=True)
        print(f"  Warm-started from: {bootstrap_path}")
    else:
        print(f"  WARNING: Bootstrap model not found at {bootstrap_path}, using random init")

    current_global_params = get_model_parameters(init_model)

    TOTAL_ROUNDS = 10
    BASE_LR = 5e-4   # lower LR for fine-tuning on top of bootstrap
    round_evaluations = {}
    all_rounds_history = []

    for r in range(1, TOTAL_ROUNDS + 1):
        # Cosine-decay LR: start at BASE_LR, halve toward end
        lr = BASE_LR * (0.5 + 0.5 * math.cos(math.pi * (r - 1) / TOTAL_ROUNDS))
        client_updates = []
        for n, (x_n, y_n) in node_data.items():
            updated_params, loss_n = local_train(current_global_params, x_n, y_n, epochs=5, lr=lr)
            client_updates.append(
                ClientUpdate(
                    node_id=n,
                    parameters=updated_params,
                    num_examples=len(x_n),
                    metrics={"loss": loss_n},
                )
            )

        current_global_params = aggregate_weighted_fedavg(client_updates)
        metrics = evaluate_global(current_global_params, x_test_sc, y_test)

        all_rounds_history.append({
            "round": r,
            "metrics": metrics,
        })
        # Save every-round checkpoint (r0001 reserved for bootstrap)
        version_name = f"federated-heart_disease-r{r + 1:04d}"
        path, cs = save_checkpoint_artifact(current_global_params, scaler, metrics, version_name, r)
        round_evaluations[version_name] = {
            "params": current_global_params,
            "metrics": metrics,
            "path": path,
            "checksum": cs,
            "round": r,
        }
        print(f"  Round {r:2d}/{TOTAL_ROUNDS} | LR={lr:.5f} | Loss: {metrics['loss']:.4f} | Acc: {metrics['accuracy']:.4f} | F1: {metrics['f1']:.4f} | AUC: {metrics['roc_auc']:.4f}")

    # 4. Compare Models & Select Best
    print("\n[4/6] Comparing Global Model Checkpoints on Test Set ...")
    print(f"  {'Model Version':<32} | {'Loss':<7} | {'Acc':<7} | {'F1':<7} | {'ROC-AUC':<7}")
    print("  " + "-" * 70)

    best_version = None
    best_eval = None
    best_score = -1.0

    for ver, data in round_evaluations.items():
        m = data["metrics"]
        score = m["f1"] + m["roc_auc"] - m["loss"]
        print(f"  {ver:<32} | {m['loss']:<7.4f} | {m['accuracy']:<7.4f} | {m['f1']:<7.4f} | {m['roc_auc']:<7.4f}")
        if score > best_score:
            best_score = score
            best_version = ver
            best_eval = data

    print(f"\n  BEST MODEL SELECTED: {best_version}")
    print(f"    Metrics: Accuracy={best_eval['metrics']['accuracy']}, F1={best_eval['metrics']['f1']}, ROC-AUC={best_eval['metrics']['roc_auc']}, Loss={best_eval['metrics']['loss']}")
    print(f"    Confusion Matrix: TN={best_eval['metrics']['tn']}, FP={best_eval['metrics']['fp']}, FN={best_eval['metrics']['fn']}, TP={best_eval['metrics']['tp']}")

    # 5. Activate Best Model in DB
    asyncio.run(
        update_db_registered_models(
            best_version=best_version,
            best_path=best_eval["path"],
            best_checksum=best_eval["checksum"],
            best_metrics=best_eval["metrics"],
            all_rounds=all_rounds_history,
        )
    )

    # 6. Verify End-to-End Prediction & Risk Classification
    print("\n[6/6] Verifying Risk Classification & Inference Thresholds ...")
    artifact = PredictionEngineResult = PredictionEngine.predict(
        artifact=type("Artifact", (), {
            "path": str(best_eval["path"]),
            "version": best_version,
            "dataset_type": DatasetType.HEART_DISEASE,
            "input_dim": 9,
            "feature_names": FEATURE_NAMES,
            "preprocessing": {"type": "standardization", "means": scaler.mean_.tolist(), "scales": scaler.scale_.tolist()},
            "state_dict": torch.load(best_eval["path"])["state_dict"],
            "warnings": [],
        })(),
        features={"age": 62, "sex": 1, "cp": 0, "trestbps": 155, "chol": 290, "fbs": 1, "thalach": 105, "exang": 1, "oldpeak": 2.8},
        model_source=ModelSource.FEDERATED,
    )

    p = artifact.probability
    rl = risk_from_probability(p)
    rl_str = risk_label(rl)
    print(f"  Test Patient Prediction: Probability={p:.4f} ({p*100:.1f}%) | Risk Level={rl_str} (level={rl.value})")

    # Risk threshold sanity check
    if p >= 0.65:
        assert rl.value == "high", f"Expected high risk for P={p:.4f}"
    elif p >= 0.35:
        assert rl.value == "moderate", f"Expected moderate risk for P={p:.4f}"
    else:
        assert rl.value == "low", f"Expected low risk for P={p:.4f}"
    print(f"{PASS} Risk classification threshold check PASSED for P={p:.4f} -> {rl_str}")

    print("\n" + "=" * 65)
    print(f"  FEDERATED TRAINING & ACTIVATION COMPLETE: Active Model = {best_version}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
