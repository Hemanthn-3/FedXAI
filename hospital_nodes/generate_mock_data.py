import pandas as pd
import numpy as np
from pathlib import Path

def generate_hospital_data(path: Path, rows: int = 100, seed: int = 42) -> None:
    """Generate deterministic healthcare mock data matching the heart disease schema."""
    np.random.seed(seed)
    records = []
    for index in range(rows):
        target = int(np.random.choice([0, 1]))
        records.append({
            "age": float(np.random.randint(30, 80)),
            "sex": float(np.random.choice([0.0, 1.0])),
            "cp": float(np.random.choice([0.0, 1.0, 2.0, 3.0])),
            "trestbps": float(np.random.randint(90, 180)),
            "chol": float(np.random.randint(150, 350)),
            "fbs": float(np.random.choice([0.0, 1.0])),
            "thalach": float(np.random.randint(100, 200)),
            "exang": float(np.random.choice([0.0, 1.0])),
            "oldpeak": float(round(np.random.uniform(0.0, 5.0), 2)),
            "target": target
        })
    df = pd.DataFrame.from_records(records)
    # Ensure both target classes are present and there are enough rows
    assert df["target"].nunique() == 2, "Mock data must contain both classes"
    assert len(df) >= 10, "Mock data must contain at least 10 valid rows"
    
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"Generated mock data for {path.parent.name} at {path}")

def main() -> None:
    base_dir = Path(__file__).resolve().parent
    generate_hospital_data(base_dir / "node_1" / "data.csv", rows=100, seed=101)
    generate_hospital_data(base_dir / "node_2" / "data.csv", rows=120, seed=102)
    generate_hospital_data(base_dir / "node_3" / "data.csv", rows=90, seed=103)

if __name__ == "__main__":
    main()
