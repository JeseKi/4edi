"""管理员领域服务。"""

from .short_transactions import (
    assert_can_create_user,
    assert_can_manage_users,
    assert_current_admin_not_in_users,
    bulk_delete_users,
    bulk_update_users,
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    list_users_by_ids,
    normalize_user_ids,
    update_user,
    update_user_scopes,
)

__all__ = [
    "assert_can_create_user",
    "assert_can_manage_users",
    "assert_current_admin_not_in_users",
    "bulk_delete_users",
    "bulk_update_users",
    "create_user",
    "delete_user",
    "get_user_by_id",
    "list_users",
    "list_users_by_ids",
    "normalize_user_ids",
    "update_user",
    "update_user_scopes",
]
