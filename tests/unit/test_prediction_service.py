from backend.app.models.patient import Patient
from backend.app.services.prediction_service import PredictionService


def test_patient_feature_payload_uses_canonical_prediction_fields() -> None:
    patient = Patient(
        age=52,
        bp=130,
        cholesterol=240,
        glucose=115,
        heart_rate=None,
        bmi=27.5,
        target=None,
    )

    assert PredictionService.patient_feature_payload(patient) == {
        "age": 52,
        "bp": 130,
        "cholesterol": 240,
        "glucose": 115,
        "bmi": 27.5,
    }
