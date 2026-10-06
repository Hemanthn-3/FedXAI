from backend.app.models.patient import Patient
from backend.app.services.prediction_service import PredictionService


def test_patient_feature_payload_uses_canonical_prediction_fields() -> None:
    patient = Patient(
        age=52,
        sex=1,
        cp=2,
        bp=130,
        cholesterol=240,
        glucose=115,
        heart_rate=150,
        fbs=0,
        exang=1,
        oldpeak=1.5,
        bmi=27.5,
        target=None,
    )

    assert PredictionService.patient_feature_payload(patient) == {
        "age": 52,
        "sex": 1,
        "cp": 2,
        "trestbps": 130,
        "chol": 240,
        "fbs": 0,
        "thalach": 150,
        "exang": 1,
        "oldpeak": 1.5,
        "glucose": 115,
        "bmi": 27.5,
    }
