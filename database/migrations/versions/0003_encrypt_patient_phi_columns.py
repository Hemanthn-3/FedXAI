"""Store sensitive patient measurements as encrypted text.

Revision ID: 0003_encrypt_patient_phi_columns
Revises: 0002_patient_hd_features
Create Date: 2026-09-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from backend.app.core.encryption import get_encryptor

revision: str = "0003_encrypt_patient_phi_columns"
down_revision: str | None = "0002_patient_hd_features"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHI_COLUMNS = ("bp", "cholesterol", "glucose", "heart_rate", "bmi")

RANGE_CONSTRAINTS = (
    "ck_patients_bmi_valid",
    "ck_patients_bp_valid",
    "ck_patients_cholesterol_valid",
    "ck_patients_glucose_valid",
    "ck_patients_heart_rate_valid",
)


def _encrypt_value(value: object) -> str | None:
    if value is None:
        return None
    return get_encryptor().encrypt(float(value))


def _decrypt_value(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value)
    return get_encryptor().decrypt(str(value))


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for column in PHI_COLUMNS:
        op.add_column("patients", sa.Column(f"{column}_encrypted_tmp", sa.Text(), nullable=True))

    patients = bind.execute(
        sa.text(
            "SELECT id, bp, cholesterol, glucose, heart_rate, bmi FROM patients"
        )
    ).mappings()
    for patient in patients:
        encrypted = {column: _encrypt_value(patient[column]) for column in PHI_COLUMNS}
        bind.execute(
            sa.text(
                """
                UPDATE patients
                SET bp_encrypted_tmp = :bp,
                    cholesterol_encrypted_tmp = :cholesterol,
                    glucose_encrypted_tmp = :glucose,
                    heart_rate_encrypted_tmp = :heart_rate,
                    bmi_encrypted_tmp = :bmi
                WHERE id = :id
                """
            ),
            {"id": patient["id"], **encrypted},
        )

    for constraint in RANGE_CONSTRAINTS:
        op.drop_constraint(constraint, "patients", type_="check")

    for column in PHI_COLUMNS:
        op.drop_column("patients", column)
        op.alter_column(
            "patients",
            f"{column}_encrypted_tmp",
            new_column_name=column,
            existing_type=sa.Text(),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for column in PHI_COLUMNS:
        op.add_column("patients", sa.Column(f"{column}_plain_tmp", sa.Float(), nullable=True))

    patients = bind.execute(
        sa.text(
            "SELECT id, bp, cholesterol, glucose, heart_rate, bmi FROM patients"
        )
    ).mappings()
    for patient in patients:
        plain = {column: _decrypt_value(patient[column]) for column in PHI_COLUMNS}
        bind.execute(
            sa.text(
                """
                UPDATE patients
                SET bp_plain_tmp = :bp,
                    cholesterol_plain_tmp = :cholesterol,
                    glucose_plain_tmp = :glucose,
                    heart_rate_plain_tmp = :heart_rate,
                    bmi_plain_tmp = :bmi
                WHERE id = :id
                """
            ),
            {"id": patient["id"], **plain},
        )

    for column in PHI_COLUMNS:
        op.drop_column("patients", column)
        op.alter_column(
            "patients",
            f"{column}_plain_tmp",
            new_column_name=column,
            existing_type=sa.Float(),
        )

    op.create_check_constraint(
        "ck_patients_bmi_valid",
        "patients",
        "bmi IS NULL OR bmi BETWEEN 5 AND 150",
    )
    op.create_check_constraint(
        "ck_patients_bp_valid",
        "patients",
        "bp IS NULL OR bp BETWEEN 20 AND 350",
    )
    op.create_check_constraint(
        "ck_patients_cholesterol_valid",
        "patients",
        "cholesterol IS NULL OR cholesterol BETWEEN 0 AND 1500",
    )
    op.create_check_constraint(
        "ck_patients_glucose_valid",
        "patients",
        "glucose IS NULL OR glucose BETWEEN 0 AND 1500",
    )
    op.create_check_constraint(
        "ck_patients_heart_rate_valid",
        "patients",
        "heart_rate IS NULL OR heart_rate BETWEEN 20 AND 300",
    )
