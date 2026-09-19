"""Add heart-disease clinical fields to patients.

Revision ID: 0002_patient_hd_features
Revises: 0001_initial_schema
Create Date: 2026-08-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_patient_hd_features"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("sex", sa.SmallInteger(), nullable=True))
    op.add_column("patients", sa.Column("cp", sa.SmallInteger(), nullable=True))
    op.add_column("patients", sa.Column("fbs", sa.SmallInteger(), nullable=True))
    op.add_column("patients", sa.Column("exang", sa.SmallInteger(), nullable=True))
    op.add_column("patients", sa.Column("oldpeak", sa.Float(), nullable=True))
    op.create_check_constraint(
        "ck_patients_sex_binary",
        "patients",
        "sex IS NULL OR sex IN (0, 1)",
    )
    op.create_check_constraint(
        "ck_patients_cp_valid",
        "patients",
        "cp IS NULL OR cp BETWEEN 0 AND 4",
    )
    op.create_check_constraint(
        "ck_patients_fbs_binary",
        "patients",
        "fbs IS NULL OR fbs IN (0, 1)",
    )
    op.create_check_constraint(
        "ck_patients_exang_binary",
        "patients",
        "exang IS NULL OR exang IN (0, 1)",
    )
    op.create_check_constraint(
        "ck_patients_oldpeak_valid",
        "patients",
        "oldpeak IS NULL OR oldpeak BETWEEN 0 AND 10",
    )


def downgrade() -> None:
    op.drop_constraint("ck_patients_oldpeak_valid", "patients", type_="check")
    op.drop_constraint("ck_patients_exang_binary", "patients", type_="check")
    op.drop_constraint("ck_patients_fbs_binary", "patients", type_="check")
    op.drop_constraint("ck_patients_cp_valid", "patients", type_="check")
    op.drop_constraint("ck_patients_sex_binary", "patients", type_="check")
    op.drop_column("patients", "oldpeak")
    op.drop_column("patients", "exang")
    op.drop_column("patients", "fbs")
    op.drop_column("patients", "cp")
    op.drop_column("patients", "sex")
