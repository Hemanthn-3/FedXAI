from backend.app.auth.rbac import Permission, permissions_for_role, role_has_permission
from backend.app.models.enums import UserRole


def test_doctor_permissions_match_required_role_contract() -> None:
    permissions = permissions_for_role(UserRole.DOCTOR)

    assert Permission.VIEW_PATIENTS.value in permissions
    assert Permission.CREATE_PREDICTION.value in permissions
    assert Permission.VIEW_EXPLANATIONS.value in permissions
    assert Permission.DOWNLOAD_REPORTS.value in permissions
    assert Permission.MANAGE_USERS.value not in permissions


def test_system_admin_can_manage_users_and_hospitals() -> None:
    assert role_has_permission(UserRole.SYSTEM_ADMIN, Permission.MANAGE_USERS)
    assert role_has_permission(UserRole.SYSTEM_ADMIN, Permission.MANAGE_HOSPITALS)
    assert role_has_permission(UserRole.SYSTEM_ADMIN, Permission.CONTROL_FL_ROUNDS)
