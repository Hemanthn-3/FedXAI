"""
FedPedia-XAI — Bootstrap Model Training Script
================================================
Trains a HealthcareMLP on all 3 hospital node CSVs combined.

Requirements satisfied:
  R1:  Exact 9 features in exact order confirmed from CSV columns
  R2:  All categorical values are numeric floats — no string encoding
  R3:  target: 0=no heart disease, 1=heart disease
  R4:  Single sigmoid logit → P(class=1) = positive-class probability
  R5:  Combined 3-node dataset
  R6:  Stratified 80/20 train/test split
  R7:  StandardScaler fitted ONLY on training split
  R8:  Scaler means_ and scale_ saved in artifact preprocessing dict
  R9:  Inference uses EXACT same scaler params (loaded from artifact)
  R10: torch.manual_seed(42) + random_state=42 for reproducibility
  R11: Reports accuracy, precision, recall, F1, ROC-AUC, confusion matrix

Usage inside Docker:
    docker cp train_bootstrap_model.py fedpedia-backend:/app/train_bootstrap_model.py
    docker exec fedpedia-backend python train_bootstrap_model.py
"""

import hashlib
import os
import random
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

from fl_server.server.model import HealthcareMLP, create_model

# ==============================================================================
#  TRAINING CONTRACT (R1–R4)
# ==============================================================================
#
#  Feature order (exact, matches DATASET_SCHEMAS in dataset.py):
FEATURE_NAMES = ("age", "sex", "cp", "trestbps", "chol", "fbs", "thalach", "exang", "oldpeak")
TARGET_COL = "target"
#
#  Categorical encoding (confirmed from CSV inspection — all numeric floats):
#    sex:    1.0=Male,       0.0=Female
#    cp:     0=Typical Angina, 1=Atypical Angina, 2=Non-anginal Pain, 3=Asymptomatic
#    fbs:    0=≤120 mg/dL,  1=>120 mg/dL
#    exang:  0=No,           1=Yes
#    target: 0=no heart disease, 1=heart disease (positive class)
#
#  PyTorch output convention:
#    Single scalar logit → sigmoid → float in [0,1]
#    This IS the probability of class 1 (heart disease positive)
#    predicted_class = int(probability >= 0.5)
#
# ==============================================================================

RANDOM_SEED = 42
EPOCHS = 150
BATCH_SIZE = 32
LEARNING_RATE = 1e-3
HIDDEN_DIMS = (32, 16)   # MUST match create_model() default in fl_server/server/model.py
DROPOUT = 0.2
PATIENCE = 20            # early stopping patience


def set_all_seeds(seed: int) -> None:
    """Deterministic training (R10)."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def load_combined_dataset() -> pd.DataFrame:
    """Load and combine all 3 hospital node CSVs (R5)."""
    # Support both Docker path and local path
    if os.path.exists("/app/hospital_nodes"):
        base = Path("/app/hospital_nodes")
    else:
        base = Path("hospital_nodes")

    frames = []
    for node in ("node_1", "node_2", "node_3"):
        csv_path = base / node / "data.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")
        df = pd.read_csv(csv_path)
        df["_source_node"] = node
        frames.append(df)
        print(f"  Loaded {node}: {len(df)} rows")

    combined = pd.concat(frames, ignore_index=True)
    before_dedup = len(combined)
    combined = combined.drop_duplicates(subset=list(FEATURE_NAMES) + [TARGET_COL])
    after_dedup = len(combined)
    print(f"  Combined: {before_dedup} rows -> {after_dedup} after deduplication")

    # Validate all required columns are present
    required = set(FEATURE_NAMES) | {TARGET_COL}
    missing_cols = required - set(combined.columns)
    if missing_cols:
        raise ValueError(f"Missing columns in combined dataset: {missing_cols}")

    # Report class balance
    pos = int(combined[TARGET_COL].sum())
    neg = len(combined) - pos
    print(f"  Class balance: {neg} negative (0), {pos} positive (1)")

    return combined


def build_datasets(df: pd.DataFrame):
    """Stratified split and scale. Scaler fitted ONLY on train (R6, R7)."""
    x = df[list(FEATURE_NAMES)].to_numpy(dtype=np.float32)
    y = df[TARGET_COL].to_numpy(dtype=np.float32)

    x_train, x_test, y_train, y_test = train_test_split(
        x, y,
        test_size=0.20,
        random_state=RANDOM_SEED,
        stratify=y,
    )
    print(f"  Train: {len(x_train)} rows | Test: {len(x_test)} rows (stratified 80/20)")

    # R7: fit scaler ONLY on training data
    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train).astype(np.float32)
    x_test_scaled = scaler.transform(x_test).astype(np.float32)

    print(f"  Scaler means : {np.round(scaler.mean_, 3).tolist()}")
    print(f"  Scaler scales: {np.round(scaler.scale_, 3).tolist()}")

    return x_train_scaled, x_test_scaled, y_train, y_test, scaler, x_train, x_test


def train_model(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
) -> HealthcareMLP:
    """Train HealthcareMLP with early stopping (R10)."""
    set_all_seeds(RANDOM_SEED)

    model = HealthcareMLP(
        input_dim=len(FEATURE_NAMES),
        hidden_dims=HIDDEN_DIMS,
        dropout=DROPOUT,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    criterion = nn.BCEWithLogitsLoss()

    x_tr = torch.as_tensor(x_train, dtype=torch.float32)
    y_tr = torch.as_tensor(y_train, dtype=torch.float32)
    x_te = torch.as_tensor(x_test, dtype=torch.float32)
    y_te = torch.as_tensor(y_test, dtype=torch.float32)

    best_val_loss = float("inf")
    best_state = None
    patience_count = 0

    for epoch in range(1, EPOCHS + 1):
        # --- training ---
        model.train()
        indices = torch.randperm(len(x_tr))
        epoch_loss = 0.0
        for start in range(0, len(x_tr), BATCH_SIZE):
            batch_idx = indices[start:start + BATCH_SIZE]
            xb, yb = x_tr[batch_idx], y_tr[batch_idx]
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(xb)
        epoch_loss /= len(x_tr)

        # --- validation ---
        model.eval()
        with torch.no_grad():
            val_loss = criterion(model(x_te), y_te).item()

        if epoch % 10 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d}/{EPOCHS} | train_loss={epoch_loss:.4f} | val_loss={val_loss:.4f}")

        # Early stopping
        if val_loss < best_val_loss - 1e-4:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_count = 0
        else:
            patience_count += 1
            if patience_count >= PATIENCE:
                print(f"  Early stopping at epoch {epoch} (patience={PATIENCE})")
                break

    if best_state is not None:
        model.load_state_dict(best_state)
        print(f"  Loaded best checkpoint (val_loss={best_val_loss:.4f})")

    return model


def evaluate_model(model: HealthcareMLP, x_test: np.ndarray, y_test: np.ndarray) -> dict:
    """Compute full test metrics (R11)."""
    model.eval()
    x_te = torch.as_tensor(x_test, dtype=torch.float32)
    with torch.no_grad():
        logits = model(x_te)
        probs = torch.sigmoid(logits).cpu().numpy().reshape(-1)

    preds = (probs >= 0.5).astype(int)
    y_int = y_test.astype(int)

    acc = accuracy_score(y_int, preds)
    prec = precision_score(y_int, preds, zero_division=0)
    rec = recall_score(y_int, preds, zero_division=0)
    f1 = f1_score(y_int, preds, zero_division=0)
    auc = roc_auc_score(y_int, probs)
    cm = confusion_matrix(y_int, preds)

    return {
        "accuracy":   acc,
        "precision":  prec,
        "recall":     rec,
        "f1":         f1,
        "roc_auc":    auc,
        "confusion_matrix": cm.tolist(),
        "tn": int(cm[0, 0]),
        "fp": int(cm[0, 1]),
        "fn": int(cm[1, 0]),
        "tp": int(cm[1, 1]),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_artifact(model: HealthcareMLP, scaler: StandardScaler, metrics: dict) -> Path:
    """Save model + scaler preprocessing params into the artifact (R8)."""
    artifact_root = Path("/app/artifacts") if os.path.exists("/app/artifacts") else Path("artifacts")
    target_dir = artifact_root / "models" / "heart_disease"
    target_dir.mkdir(parents=True, exist_ok=True)

    version = "federated-heart_disease-r0001-bootstrap"
    model_path = target_dir / f"{version}.pt"

    # R8: Save scaler means and scales alongside model weights
    preprocessing = {
        "type":   "standardization",
        "means":  scaler.mean_.tolist(),    # fitted on training split only
        "scales": scaler.scale_.tolist(),   # fitted on training split only
    }

    torch.save(
        {
            "version":        version,
            "dataset_type":   "heart_disease",
            "round_number":   1,
            "input_dim":      len(FEATURE_NAMES),
            "feature_names":  list(FEATURE_NAMES),
            "preprocessing":  preprocessing,
            "metrics": {
                "accuracy":  round(metrics["accuracy"], 4),
                "precision": round(metrics["precision"], 4),
                "recall":    round(metrics["recall"], 4),
                "f1":        round(metrics["f1"], 4),
                "roc_auc":   round(metrics["roc_auc"], 4),
            },
            "state_dict":     model.state_dict(),
        },
        model_path,
    )
    checksum = sha256(model_path)
    print(f"  Saved: {model_path}")
    print(f"  SHA-256: {checksum}")
    return model_path


def main() -> None:
    print("\n" + "=" * 65)
    print("  FedPedia-XAI - Bootstrap Model Training")
    print("=" * 65)

    # Step 1: Load data
    print("\n[1/5] Loading combined dataset ...")
    df = load_combined_dataset()

    # Step 2: Split + scale
    print("\n[2/5] Stratified split + StandardScaler fit on train only ...")
    x_train_sc, x_test_sc, y_train, y_test, scaler, x_train_raw, x_test_raw = build_datasets(df)

    # Step 3: Train
    print(f"\n[3/5] Training HealthcareMLP for up to {EPOCHS} epochs (seed={RANDOM_SEED}) ...")
    model = train_model(x_train_sc, y_train, x_test_sc, y_test)

    # Step 4: Evaluate
    print("\n[4/5] Evaluating on held-out test set ...")
    metrics = evaluate_model(model, x_test_sc, y_test)
    print()
    print("  TEST METRICS")
    print(f"  {'Accuracy':<12}: {metrics['accuracy']:.4f}")
    print(f"  {'Precision':<12}: {metrics['precision']:.4f}")
    print(f"  {'Recall':<12}: {metrics['recall']:.4f}")
    print(f"  {'F1':<12}: {metrics['f1']:.4f}")
    print(f"  {'ROC-AUC':<12}: {metrics['roc_auc']:.4f}")
    print(f"  Confusion matrix (rows=actual, cols=predicted):")
    print(f"    TN={metrics['tn']}  FP={metrics['fp']}")
    print(f"    FN={metrics['fn']}  TP={metrics['tp']}")

    # Step 5: Save
    print("\n[5/5] Saving artifact ...")
    save_artifact(model, scaler, metrics)

    print("\n" + "=" * 65)
    print("  Training complete. Run verify_pipeline.py next.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
