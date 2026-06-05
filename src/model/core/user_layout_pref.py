from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.database import db


class UserLayoutPref(db.Model):
    """
    Persiste preferências de layout de uma SmartList por usuário.
    """

    __tablename__ = "user_layout_pref"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),  # ← "users", não "user"
        nullable=False, index=True
    )

    list_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    layout_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    visible_to_all: Mapped[bool] = mapped_column(
        db.Boolean, default=False, nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "list_id", name="uq_user_layout"),
    )

    @property
    def layout(self) -> dict:
        try:
            return json.loads(self.layout_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @layout.setter
    def layout(self, value: dict) -> None:
        self.layout_json = json.dumps(value, ensure_ascii=False)

    @classmethod
    def get_for_user(cls, user_id: int, list_id: str) -> "UserLayoutPref | None":
        return cls.query.filter_by(user_id=user_id, list_id=list_id).first()

    @classmethod
    def save_for_user(cls, user_id: int, list_id: str, layout: dict) -> "UserLayoutPref":
        pref = cls.get_for_user(user_id, list_id)
        if pref is None:
            pref = cls(user_id=user_id, list_id=list_id)
            db.session.add(pref)
        pref.layout = layout
        pref.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return pref

    @classmethod
    def delete_for_user(cls, user_id: int, list_id: str) -> bool:
        pref = cls.get_for_user(user_id, list_id)
        if pref:
            db.session.delete(pref)
            db.session.commit()
            return True
        return False

    def __repr__(self) -> str:
        return f"<UserLayoutPref user={self.user_id} list={self.list_id}>"