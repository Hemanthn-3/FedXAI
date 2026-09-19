# Federated Learning Guide

## Phase 3 scope

Phase 3 implements the federated-learning runtime for FedPedia-XAI:

- Flower server runtime
- FedAvg and Weighted FedAvg aggregation
- Versioned global model artifacts
- Durable JSONL training-round metrics
- Three hospital client entrypoints
- Local dataset validation and preprocessing inside hospital nodes
- Local PyTorch MLP training and evaluation

Prediction APIs, SHAP, LIME, dashboards, and Docker orchestration are delivered
in later phases.

## Privacy boundary

Raw hospital CSV files are loaded only by hospital-node processes. The Flower
server receives:

- model parameter arrays;
- number of local training examples;
- scalar metrics such as loss, accuracy, precision, recall, F1, and ROC-AUC;
- a node identifier such as `hospital_1`.

The server does not receive patient rows, feature values, or hospital-local
preprocessing objects.

## Supported datasets

### Heart Disease

Required columns:

```text
age, sex, cp, trestbps, chol, fbs, thalach, exang, oldpeak, target
```

### Diabetes

Required columns:

```text
pregnancies, glucose, bloodpressure, insulin, bmi, age, outcome
```

### Breast Cancer

Required columns:

```text
radius, texture, perimeter, area, smoothness, diagnosis
```

`diagnosis` accepts binary values or textual values such as `B`, `benign`, `M`,
and `malignant`.

## Configuration

Default values match the project specification:

```text
FL_ROUNDS=20
FL_CLIENTS=3
FL_EPOCHS=5
FL_BATCH_SIZE=32
FL_LR=0.001
FL_AGGREGATION_STRATEGY=fedavg
FL_DATASET_TYPE=heart_disease
FL_ARTIFACT_ROOT=artifacts/models
```

`fedavg` gives equal weight to each participating hospital. `weighted_fedavg`
weights each update by the hospital's local training-example count.

## Running locally

Start the server:

```powershell
python -m fl_server.server.app --server-address 127.0.0.1:8080 --rounds 20 --clients 3
```

Start three hospital clients in separate terminals:

```powershell
python -m hospital_nodes.node_1.client --data-path C:\path\hospital_1.csv --dataset-type heart_disease --server-address 127.0.0.1:8080
python -m hospital_nodes.node_2.client --data-path C:\path\hospital_2.csv --dataset-type heart_disease --server-address 127.0.0.1:8080
python -m hospital_nodes.node_3.client --data-path C:\path\hospital_3.csv --dataset-type heart_disease --server-address 127.0.0.1:8080
```

Each hospital CSV must contain the schema required by the selected dataset
type. A missing file fails fast with a clear error instead of silently creating
fake data.

## Artifacts

After each successful round the server writes:

- `artifacts/models/<dataset>/<model-version>.pt`
- `artifacts/models/training_rounds.jsonl`

The `.pt` file contains:

- model version;
- dataset type;
- round number;
- input dimension;
- aggregate metrics;
- PyTorch `state_dict`.

The server computes and records a SHA-256 checksum for every global model.

## Extension points

- Differential privacy can be applied in `HospitalFlowerClient.fit` before
  parameters leave the client.
- Secure aggregation can replace the plain parameter transport between client
  and strategy.
- Homomorphic encryption can be introduced as a new transport/strategy pair.
- Later dashboard work can read `training_rounds.jsonl` or persist the same
  metrics into PostgreSQL through the backend.
