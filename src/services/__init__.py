"""
Camada de serviços com regras de negócio desacopladas dos blueprints.
"""

from .notifications_service import (
    create_notification,
    delete_trash_entry,
    list_notifications,
    list_trash,
    mark_as_read,
    mark_as_unread,
    move_to_trash,
    restore_from_trash,
)
from .profile_service import (
    change_password,
    update_notification_preferences_from_form,
    update_notification_preferences_from_json,
    update_profile_from_form,
    update_profile_from_json,
)

__all__ = [
    "update_profile_from_form",
    "update_profile_from_json",
    "update_notification_preferences_from_form",
    "update_notification_preferences_from_json",
    "change_password",
    "create_notification",
    "list_notifications",
    "mark_as_read",
    "mark_as_unread",
    "move_to_trash",
    "list_trash",
    "restore_from_trash",
    "delete_trash_entry",
]
