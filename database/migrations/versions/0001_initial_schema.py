"""Create the initial FedPedia-XAI relational schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

user_role = postgresql.ENUM(
    "doctor",
    "hospital_admin",
    "system_admin",
    "researcher",
    name="user_role",
    create_type=False,
)
hospital_status = postgresql.ENUM(
    "offline",
    "online",
    "training",
    "error",
    name="hospital_status",
    create_type=False,
)
dataset_type = postgresql.ENUM(
    "heart_disease",
    "diabetes",
    "breast_cancer",
    name="dataset_type",
    create_type=False,
)
risk_level = postgresql.ENUM(
    "low",
    "moderate",
    "high",
    name="risk_level",
    create_type=False,
)
training_round_status = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
    name="training_round_status",
    create_type=False,
)
aggregation_strategy = postgresql.ENUM(
    "fedavg",
    "weighted_fedavg",
    name="aggregation_strategy",
    create_type=False,
)
model_framework = postgresql.ENUM(
    "pytorch",
    "scikit_learn",
    "xgboost",
    name="model_framework",
    create_type=False,
)
model_source = postgresql.ENUM(
    "federated",
    "centralized",
    name="model_source",
    create_type=False,
)
xai_status = postgresql.ENUM(
    "pending",
    "completed",
    "failed",
    name="xai_status",
    create_type=False,
)


def _create_enums() -> None:
    bind = op.get_bind()
    for enum in (
        user_role,
        hospital_status,
        dataset_type,
        risk_level,
        training_round_status,
        aggregation_strategy,
        model_framework,
        model_source,
        xai_status,
    ):
        enum.create(bind, checkfirst=True)


def upgrade() -> None:
    _create_enums()

    op.create_table(
        "hospitals",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("node_id", sa.String(length=80), nullable=False),
        sa.Column(
            "status",
            hospital_status,
            server_default="offline",
            nullable=False,
        ),
        sa.Column("id", UUID, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(name)) >= 2", name="ck_hospitals_name_min_length"),
        sa.CheckConstraint(
            "length(trim(node_id)) >= 3",
            name="ck_hospitals_node_id_min_length",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_hospitals"),
        sa.UniqueConstraint("name", name="uq_hospitals_name"),
        sa.UniqueConstraint("node_id", name="uq_hospitals_node_id"),
    )
    op.create_index("ix_hospitals_node_id", "hospitals", ["node_id"], unique=False)
    op.create_index("ix_hospitals_status", "hospitals", ["status"], unique=False)

    op.create_table(
        "global_models",
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("dataset_type", dataset_type, nullable=False),
        sa.Column("framework", model_framework, nullable=False),
        sa.Column("source", model_source, nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", UUID, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(version)) >= 1",
            name="ck_global_models_version_not_blank",
        ),
        sa.CheckConstraint(
            "length(checksum_sha256) = 64",
            name="ck_global_models_checksum_sha256_length",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_global_models"),
        sa.UniqueConstraint("version", name="uq_global_models_version"),
    )
    op.create_index(
        "ix_global_models_dataset_type",
        "global_models",
        ["dataset_type"],
        unique=False,
    )
    op.create_index("ix_global_models_is_active", "global_models", ["is_active"], unique=False)
    op.create_index("ix_global_models_source", "global_models", ["source"], unique=False)
    op.create_index("ix_global_models_version", "global_models", ["version"], unique=False)
    op.create_index(
        "uq_global_models_active_dataset_source",
        "global_models",
        ["dataset_type", "source"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_table(
        "users",
        sa.Column("hospital_id", UUID, nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", UUID, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        sa.CheckConstraint("length(trim(name)) >= 2", name="ck_users_name_min_length"),
        sa.CheckConstraint(
            "((role IN ('doctor', 'hospital_admin') AND hospital_id IS NOT NULL) "
            "OR (role IN ('system_admin', 'researcher')))",
            name="ck_users_hospital_role_scope",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id"],
            ["hospitals.id"],
            name="fk_users_hospital_id_hospitals",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index("ix_users_hospital_id", "users", ["hospital_id"], unique=False)
    op.create_index("ix_users_is_active", "users", ["is_active"], unique=False)
    op.create_index("ix_users_role", "users", ["role"], unique=False)

    op.create_table(
        "patients",
        sa.Column("hospital_id", UUID, nullable=False),
        sa.Column("external_reference", sa.String(length=120), nullable=True),
        sa.Column("age", sa.SmallInteger(), nullable=False),
        sa.Column("bp", sa.Float(), nullable=True),
        sa.Column("cholesterol", sa.Float(), nullable=True),
        sa.Column("glucose", sa.Float(), nullable=True),
        sa.Column("heart_rate", sa.Float(), nullable=True),
        sa.Column("bmi", sa.Float(), nullable=True),
        sa.Column("target", sa.SmallInteger(), nullable=True),
        sa.Column("id", UUID, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("age BETWEEN 0 AND 130", name="ck_patients_age_valid"),
        sa.CheckConstraint(
            "bmi IS NULL OR bmi BETWEEN 5 AND 150",
            name="ck_patients_bmi_valid",
        ),
        sa.CheckConstraint(
            "bp IS NULL OR bp BETWEEN 20 AND 350",
            name="ck_patients_bp_valid",
        ),
        sa.CheckConstraint(
            "cholesterol IS NULL OR cholesterol BETWEEN 0 AND 1500",
            name="ck_patients_cholesterol_valid",
        ),
        sa.CheckConstraint(
            "glucose IS NULL OR glucose BETWEEN 0 AND 1500",
            name="ck_patients_glucose_valid",
        ),
        sa.CheckConstraint(
            "heart_rate IS NULL OR heart_rate BETWEEN 20 AND 300",
            name="ck_patients_heart_rate_valid",
        ),
        sa.CheckConstraint(
            "target IS NULL OR target IN (0, 1)",
            name="ck_patients_target_binary",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id"],
            ["hospitals.id"],
            name="fk_patients_hospital_id_hospitals",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_patients"),
        sa.UniqueConstraint(
            "hospital_id",
            "external_reference",
            name="uq_patients_hospital_external_reference",
        ),
    )
    op.create_index("ix_patients_hospital_id", "patients", ["hospital_id"], unique=False)

    op.create_table(
        "training_rounds",
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("global_model_id", UUID, nullable=True),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("dataset_type", dataset_type, nullable=False),
        sa.Column(
            "aggregation_strategy",
            aggregation_strategy,
            server_default="fedavg",
            nullable=False,
        ),
        sa.Column(
            "status",
            training_round_status,
            server_default="pending",
            nullable=False,
        ),
        sa.Column("total_clients", sa.Integer(), nullable=False),
        sa.Column("participating_clients", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "participating_nodes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "client_metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("precision", sa.Float(), nullable=True),
        sa.Column("recall", sa.Float(), nullable=True),
        sa.Column("f1", sa.Float(), nullable=True),
        sa.Column("roc_auc", sa.Float(), nullable=True),
        sa.Column("loss", sa.Float(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", UUID, nullable=False),
        sa.CheckConstraint(
            "accuracy IS NULL OR accuracy BETWEEN 0 AND 1",
            name="ck_training_rounds_accuracy_unit",
        ),
        sa.CheckConstraint(
            "f1 IS NULL OR f1 BETWEEN 0 AND 1",
            name="ck_training_rounds_f1_unit",
        ),
        sa.CheckConstraint(
            "loss IS NULL OR loss >= 0",
            name="ck_training_rounds_loss_non_negative",
        ),
        sa.CheckConstraint(
            "participating_clients BETWEEN 0 AND total_clients",
            name="ck_training_rounds_participating_clients_valid",
        ),
        sa.CheckConstraint(
            "precision IS NULL OR precision BETWEEN 0 AND 1",
            name="ck_training_rounds_precision_unit",
        ),
        sa.CheckConstraint(
            "recall IS NULL OR recall BETWEEN 0 AND 1",
            name="ck_training_rounds_recall_unit",
        ),
        sa.CheckConstraint(
            "roc_auc IS NULL OR roc_auc BETWEEN 0 AND 1",
            name="ck_training_rounds_roc_auc_unit",
        ),
        sa.CheckConstraint(
            "round_number > 0",
            name="ck_training_rounds_round_number_positive",
        ),
        sa.CheckConstraint(
            "total_clients > 0",
            name="ck_training_rounds_total_clients_positive",
        ),
        sa.ForeignKeyConstraint(
            ["global_model_id"],
            ["global_models.id"],
            name="fk_training_rounds_global_model_id_global_models",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_training_rounds"),
        sa.UniqueConstraint("run_id", "round_number", name="uq_training_rounds_run_round"),
    )
    op.create_index(
        "ix_training_rounds_dataset_type",
        "training_rounds",
        ["dataset_type"],
        unique=False,
    )
    op.create_index(
        "ix_training_rounds_global_model_id",
        "training_rounds",
        ["global_model_id"],
        unique=False,
    )
    op.create_index("ix_training_rounds_run_id", "training_rounds", ["run_id"], unique=False)
    op.create_index("ix_training_rounds_status", "training_rounds", ["status"], unique=False)
    op.create_index(
        "ix_training_rounds_timestamp",
        "training_rounds",
        ["timestamp"],
        unique=False,
    )

    op.create_table(
        "predictions",
        sa.Column("patient_id", UUID, nullable=False),
        sa.Column("global_model_id", UUID, nullable=True),
        sa.Column("dataset_type", dataset_type, nullable=False),
        sa.Column("model_source", model_source, nullable=False),
        sa.Column("input_features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("prediction", sa.SmallInteger(), nullable=False),
        sa.Column("doctor_notes", sa.Text(), nullable=True),
        sa.Column("id", UUID, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "prediction IN (0, 1)",
            name="ck_predictions_prediction_binary",
        ),
        sa.CheckConstraint(
            "probability BETWEEN 0 AND 1",
            name="ck_predictions_probability_unit",
        ),
        sa.ForeignKeyConstraint(
            ["global_model_id"],
            ["global_models.id"],
            name="fk_predictions_global_model_id_global_models",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            name="fk_predictions_patient_id_patients",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_predictions"),
    )
    op.create_index(
        "ix_predictions_dataset_type",
        "predictions",
        ["dataset_type"],
        unique=False,
    )
    op.create_index(
        "ix_predictions_global_model_id",
        "predictions",
        ["global_model_id"],
        unique=False,
    )
    op.create_index(
        "ix_predictions_model_source",
        "predictions",
        ["model_source"],
        unique=False,
    )
    op.create_index(
        "ix_predictions_patient_id",
        "predictions",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_predictions_risk_level",
        "predictions",
        ["risk_level"],
        unique=False,
    )

    op.create_table(
        "xai_reports",
        sa.Column("prediction_id", UUID, nullable=False),
        sa.Column("shap_path", sa.String(length=1024), nullable=True),
        sa.Column("lime_path", sa.String(length=1024), nullable=True),
        sa.Column("feature_ranking", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "local_contributions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("status", xai_status, server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", UUID, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["prediction_id"],
            ["predictions.id"],
            name="fk_xai_reports_prediction_id_predictions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_xai_reports"),
        sa.UniqueConstraint("prediction_id", name="uq_xai_reports_prediction_id"),
    )
    op.create_index(
        "ix_xai_reports_prediction_id",
        "xai_reports",
        ["prediction_id"],
        unique=False,
    )
    op.create_index("ix_xai_reports_status", "xai_reports", ["status"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("user_id", UUID, nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=True),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", UUID, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_audit_logs_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index(
        "ix_audit_logs_resource_type",
        "audit_logs",
        ["resource_type"],
        unique=False,
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"], unique=False)
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"], unique=False)

    op.execute(
        """
        CREATE FUNCTION prevent_audit_log_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation")

    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_xai_reports_status", table_name="xai_reports")
    op.drop_index("ix_xai_reports_prediction_id", table_name="xai_reports")
    op.drop_table("xai_reports")

    op.drop_index("ix_predictions_risk_level", table_name="predictions")
    op.drop_index("ix_predictions_patient_id", table_name="predictions")
    op.drop_index("ix_predictions_model_source", table_name="predictions")
    op.drop_index("ix_predictions_global_model_id", table_name="predictions")
    op.drop_index("ix_predictions_dataset_type", table_name="predictions")
    op.drop_table("predictions")

    op.drop_index("ix_training_rounds_timestamp", table_name="training_rounds")
    op.drop_index("ix_training_rounds_status", table_name="training_rounds")
    op.drop_index("ix_training_rounds_run_id", table_name="training_rounds")
    op.drop_index("ix_training_rounds_global_model_id", table_name="training_rounds")
    op.drop_index("ix_training_rounds_dataset_type", table_name="training_rounds")
    op.drop_table("training_rounds")

    op.drop_index("ix_patients_hospital_id", table_name="patients")
    op.drop_table("patients")

    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_hospital_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index(
        "uq_global_models_active_dataset_source",
        table_name="global_models",
        postgresql_where=sa.text("is_active = true"),
    )
    op.drop_index("ix_global_models_version", table_name="global_models")
    op.drop_index("ix_global_models_source", table_name="global_models")
    op.drop_index("ix_global_models_is_active", table_name="global_models")
    op.drop_index("ix_global_models_dataset_type", table_name="global_models")
    op.drop_table("global_models")

    op.drop_index("ix_hospitals_status", table_name="hospitals")
    op.drop_index("ix_hospitals_node_id", table_name="hospitals")
    op.drop_table("hospitals")

    bind = op.get_bind()
    for enum in (
        xai_status,
        model_source,
        model_framework,
        aggregation_strategy,
        training_round_status,
        risk_level,
        dataset_type,
        hospital_status,
        user_role,
    ):
        enum.drop(bind, checkfirst=True)
