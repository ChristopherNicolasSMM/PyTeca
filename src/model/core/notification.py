# model/notification.py
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from db.database import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(255), nullable=True)  # Novo campo: título opcional
    message = Column(Text, nullable=False)
    notification_type = Column(
        String(50), default="info"
    )  # info, success, warning, error, system
    is_read = Column(Boolean, default=False, index=True)
    action_url = Column(String(500), nullable=True)  # URL para redirecionamento
    action_params = Column(JSON, nullable=True)  # Parâmetros para a ação
    icon = Column(String(100), nullable=True)  # Ícone Bootstrap
    priority = Column(Integer, default=0)  # 0=normal, 1=alta, 2=urgente
    created_at = Column(DateTime, default=func.now(), index=True)

    __table_args__ = (
        Index("idx_notifications_user_unread", "user_id", "is_read"),
        Index("idx_notifications_priority", "priority"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "message": self.message,
            "notification_type": self.notification_type,
            "is_read": self.is_read,
            "action_url": self.action_url,
            "action_params": self.action_params or {},
            "icon": self.icon,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "time_ago": self.get_time_ago(),
        }

    def get_time_ago(self):
        """Retorna tempo relativo (há 5 minutos, há 1 hora, etc.)"""
        from datetime import datetime

        now = datetime.now()
        diff = now - self.created_at

        if diff.days > 0:
            return f"há {diff.days} dia(s)"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"há {hours} hora(s)"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"há {minutes} minuto(s)"
        else:
            return "agora mesmo"


class NotificationTrash(db.Model):
    __tablename__ = "notifications_trash"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_notification_id = Column(Integer, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), default="info")
    is_read = Column(Boolean, default=False)
    action_url = Column(String(500), nullable=True)
    action_params = Column(JSON, nullable=True)
    icon = Column(String(100), nullable=True)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime)
    trashed_at = Column(DateTime, default=func.now(), index=True)

    __table_args__ = (Index("idx_notifications_trash_user", "user_id"),)

    def to_dict(self):
        return {
            "id": self.id,
            "original_notification_id": self.original_notification_id,
            "user_id": self.user_id,
            "title": self.title,
            "message": self.message,
            "notification_type": self.notification_type,
            "is_read": self.is_read,
            "action_url": self.action_url,
            "action_params": self.action_params or {},
            "icon": self.icon,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "trashed_at": self.trashed_at.isoformat() if self.trashed_at else None,
        }
