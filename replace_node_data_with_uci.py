"""
replace_node_data_with_uci.py
=============================
Downloads the real UCI Cleveland Heart Disease dataset (303 rows),
selects the 9 model features, fixes encodings, binarizes the target,
then distributes across the 3 hospital node CSVs and copies them into Docker.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── Step 1: Download real UCI Cleveland dataset ────────────────────────────
UCI_URL = (
    "https://archive.ics.uci.edu/ml/machine-learning-databases/"
    "heart-disease/processed.cleveland.data"
)
UCI_COLS = [
    "age", "sex", "cp", "trestbps", "chol", "fbs",
    "restecg", "thalach", "exang", "oldpeak", "slope", "ca", "thal", "target",
]
MODEL_FEATURES = ["age", "sex", "cp", "trestbps", "chol", "fbs", "thalach", "exang", "oldpeak"]
TARGET_COL = "target"

print("\n" + "=" * 65)
print("  Replacing Mock Node Data with Real UCI Cleveland Dataset")
print("=" * 65)

print("\n[1/5] Downloading UCI Cleveland Heart Disease dataset ...")
raw = pd.read_csv(UCI_URL, names=UCI_COLS, na_values="?")
print(f"  Raw shape: {raw.shape}")

# ── Step 2: Pre-process ────────────────────────────────────────────────────
print("\n[2/5] Pre-processing ...")

# Drop rows with missing values in any of the 9 model features or target
subset_cols = MODEL_FEATURES + [TARGET_COL]
before = len(raw)
df = raw[subset_cols].dropna()
print(f"  Rows after dropping NA: {before} -> {len(df)}")

# Re-encode cp: UCI uses 1–4, model expects 0–3 (subtract 1)
# cp: 1=Typical Angina → 0, 2=Atypical → 1, 3=Non-anginal → 2, 4=Asymptomatic → 3
df = df.copy()
df["cp"] = (df["cp"] - 1).astype(float)
print(f"  cp range after re-encode: {df['cp'].min()}–{df['cp'].max()} (expected 0–3)")

# Binarize target: UCI 0=no disease, 1-4=disease → 0/1
df["target"] = (df["target"] > 0).astype(int)
pos = int(df["target"].sum())
neg = len(df) - pos
print(f"  Target: 0={neg} (no disease), 1={pos} (disease)")
print(f"  Class balance: {pos / len(df) * 100:.1f}% positive")

# Ensure all columns are float (except target which is int)
for col in MODEL_FEATURES:
    df[col] = df[col].astype(float)

print(f"\n  Final dataset: {len(df)} rows × {len(df.columns)} columns")
print(df.head(3).to_string())

# ── Step 3: Split into 3 hospital node CSVs ────────────────────────────────
print("\n[3/5] Splitting into 3 hospital node partitions (stratified) ...")

# Stratified split: ~100, ~100, ~103 rows per node
from sklearn.model_selection import train_test_split

# First split: 2/3 vs 1/3
part_a, node_3_df = train_test_split(df, test_size=1/3, random_state=42, stratify=df[TARGET_COL])
# Second split: 1/2 vs 1/2 of part_a
node_1_df, node_2_df = train_test_split(part_a, test_size=0.5, random_state=42, stratify=part_a[TARGET_COL])

for name, node_df in [("node_1", node_1_df), ("node_2", node_2_df), ("node_3", node_3_df)]:
    pos = int(node_df[TARGET_COL].sum())
    neg = len(node_df) - pos
    print(f"  {name}: {len(node_df)} rows | 0={neg}, 1={pos}")

# ── Step 4: Save updated CSVs ──────────────────────────────────────────────
print("\n[4/5] Saving updated CSVs ...")
base = Path("hospital_nodes")
for name, node_df in [("node_1", node_1_df), ("node_2", node_2_df), ("node_3", node_3_df)]:
    path = base / name / "data.csv"
    node_df.reset_index(drop=True).to_csv(path, index=False, float_format="%.2f")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"  Saved {path}: {len(node_df)} rows | SHA256={sha[:16]}...")

# ── Step 5: Copy into Docker container ────────────────────────────────────
print("\n[5/5] Copying updated CSVs into Docker container ...")
for name in ("node_1", "node_2", "node_3"):
    src = str(base / name / "data.csv")
    dst = f"fedpedia-backend:/app/hospital_nodes/{name}/data.csv"
    result = subprocess.run(["docker", "cp", src, dst], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  [+] Copied {src} → container")
    else:
        print(f"  [!] Failed to copy {src}: {result.stderr}")

print("\n" + "=" * 65)
print("  UCI data installed. Now run train_bootstrap_model.py and run_federated_rounds.py")
print("=" * 65 + "\n")
