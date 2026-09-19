"""Role based access control policy."""

from enum import Enum

from backend.app.models.enums import UserRole


class Permission(str, Enum):
    VIEW_PATIENTS = "patients:view"
    CREATE_PREDICTION = "predictions:create"
    VIEW_EXPLANATIONS = "xai:view"
    DOWNLOAD_REPORTS = "reports:download"
    UPLOAD_DATASETS = "datasets:upload"
    START_TRAINING = "training:start"
    MONITOR_HOSPITAL_NODE = "hospital_nodes:monitor"
    VIEW_METRICS = "metrics:view"
    MANAGE_HOSPITALS = "hospitals:manage"
    MANAGE_USERS = "users:manage"
    CONTROL_FL_ROUNDS = "fl_rounds:control"
    MONITOR_AGGREGATION = "aggregation:monitor"
    COMPARE_MODELS = "models:compare"
    ANALYZE_FAIRNESS = "fairness:analyze"
    ANALYZE_PERFORMANCE = "performance:analyze"
    GENERATE_REPORTS = "reports:generate"


ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.DOCTOR: frozenset(
        {
            Permission.VIEW_PATIENTS,
            Permission.CREATE_PREDICTION,
            Permission.VIEW_EXPLANATIONS,
            Permission.DOWNLOAD_REPORTS,
            Permission.VIEW_METRICS,
            Permission.GENERATE_REPORTS,
        }
    ),
    UserRole.HOSPITAL_ADMIN: frozenset(
        {
            Permission.UPLOAD_DATASETS,
            Permission.START_TRAINING,
            Permission.MONITOR_HOSPITAL_NODE,
            Permission.VIEW_METRICS,
            Permission.VIEW_PATIENTS,
            Permission.CREATE_PREDICTION,
            Permission.VIEW_EXPLANATIONS,
            Permission.DOWNLOAD_REPORTS,
            Permission.GENERATE_REPORTS,
        }
    ),
    UserRole.SYSTEM_ADMIN: frozenset(
        {
            Permission.MANAGE_HOSPITALS,
            Permission.MANAGE_USERS,
            Permission.CONTROL_FL_ROUNDS,
            Permission.MONITOR_AGGREGATION,
            Permission.VIEW_METRICS,
            Permission.VIEW_PATIENTS,
            Permission.GENERATE_REPORTS,
            Permission.CREATE_PREDICTION,
            Permission.VIEW_EXPLANATIONS,
            Permission.DOWNLOAD_REPORTS,
            Permission.ANALYZE_FAIRNESS,
            Permission.COMPARE_MODELS,
            Permission.ANALYZE_PERFORMANCE,
            Permission.UPLOAD_DATASETS,
            Permission.START_TRAINING,
            Permission.MONITOR_HOSPITAL_NODE,
        }
    ),
    UserRole.RESEARCHER: frozenset(
        {
            Permission.COMPARE_MODELS,
            Permission.ANALYZE_FAIRNESS,
            Permission.ANALYZE_PERFORMANCE,
            Permission.GENERATE_REPORTS,
            Permission.VIEW_METRICS,
        }
    ),
}


def permissions_for_role(role: UserRole) -> list[str]:
    """Return stable string permissions for a role."""

    return sorted(permission.value for permission in ROLE_PERMISSIONS[role])


def role_has_permission(role: UserRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]
