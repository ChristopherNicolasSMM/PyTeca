"""
Rotinas de negócio para notificações dos usuários.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from db.database import db
from model.core.notification import Notification, NotificationTrash

logger = logging.getLogger(__name__)


def create_notification(
    user_id: int, message: str, title: Optional[str] = None, **kwargs
) -> Notification:
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=kwargs.get("notification_type", "info"),
        action_url=kwargs.get("action_url"),
        action_params=kwargs.get("action_params"),
        icon=kwargs.get("icon"),
        priority=kwargs.get("priority", 0),
    )
    db.session.add(notification)
    db.session.commit()
    logger.info("Notificação %s criada para usuário %s.", notification.id, user_id)
    return notification


def list_notifications(
    user_id: int, status: Optional[str] = None
) -> List[Notification]:
    query = Notification.query.filter_by(user_id=user_id)
    if status == "read":
        query = query.filter_by(is_read=True)
    elif status == "unread":
        query = query.filter_by(is_read=False)
    return query.order_by(Notification.created_at.desc()).all()


def mark_as_read(user_id: int, notification_id: int) -> Notification:
    notification = Notification.query.filter_by(
        id=notification_id, user_id=user_id
    ).first()
    if not notification:
        raise ValueError("Notificação não encontrada")
    notification.is_read = True
    db.session.commit()
    logger.debug("Notificação %s marcada como lida.", notification_id)
    return notification


def mark_as_unread(user_id: int, notification_id: int) -> Notification:
    notification = Notification.query.filter_by(
        id=notification_id, user_id=user_id
    ).first()
    if not notification:
        raise ValueError("Notificação não encontrada")
    notification.is_read = False
    db.session.commit()
    logger.debug("Notificação %s marcada como não lida.", notification_id)
    return notification


def move_to_trash(user_id: int, notification_id: int) -> NotificationTrash:
    notification = Notification.query.filter_by(
        id=notification_id, user_id=user_id
    ).first()
    if not notification:
        raise ValueError("Notificação não encontrada")
    trashed = NotificationTrash(
        original_notification_id=notification.id,
        user_id=notification.user_id,
        title=notification.title,
        message=notification.message,
        notification_type=notification.notification_type,
        is_read=notification.is_read,
        action_url=notification.action_url,
        action_params=notification.action_params,
        icon=notification.icon,
        priority=notification.priority,
        created_at=notification.created_at,
    )
    db.session.add(trashed)
    db.session.delete(notification)
    db.session.commit()
    logger.info("Notificação %s movida para a lixeira.", notification_id)
    return trashed


def list_trash(user_id: int) -> List[NotificationTrash]:
    return (
        NotificationTrash.query.filter_by(user_id=user_id)
        .order_by(NotificationTrash.trashed_at.desc())
        .all()
    )


def restore_from_trash(user_id: int, trash_id: int) -> Notification:
    trash_entry = NotificationTrash.query.filter_by(
        id=trash_id, user_id=user_id
    ).first()
    if not trash_entry:
        raise ValueError("Item da lixeira não encontrado")
    notification = Notification(
        user_id=trash_entry.user_id,
        message=trash_entry.message,
        title=trash_entry.title,
        notification_type=trash_entry.notification_type,
        is_read=trash_entry.is_read,
        action_url=trash_entry.action_url,
        action_params=trash_entry.action_params,
        icon=trash_entry.icon,
        priority=trash_entry.priority,
        created_at=trash_entry.created_at,
    )
    db.session.add(notification)
    db.session.delete(trash_entry)
    db.session.commit()
    logger.info("Notificação %s restaurada da lixeira.", notification.id)
    return notification


def delete_trash_entry(user_id: int, trash_id: int) -> None:
    trash_entry = NotificationTrash.query.filter_by(
        id=trash_id, user_id=user_id
    ).first()
    if not trash_entry:
        raise ValueError("Item da lixeira não encontrado")
    db.session.delete(trash_entry)
    db.session.commit()
    logger.info("Item da lixeira %s removido.", trash_id)
