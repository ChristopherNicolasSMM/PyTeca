from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.database import db


class BookStatus(str, PyEnum):
    """Status do livro no ciclo de vida."""

    DRAFT = "draft"      # Rascunho — criado mas não publicado
    ACTIVE = "active"    # Publicado / disponível
    TRASH = "trash"      # Lixeira — soft-deleted


class Book(db.Model):
    """
    Modelo de Livro.

    Ciclo de status:
        DRAFT  →  ACTIVE  →  TRASH
                             (pode ser restaurado para ACTIVE)

    O rascunho é criado automaticamente quando o usuário começa a preencher
    o formulário e vai sendo salvo via auto-save antes de publicar.
    """

    __tablename__ = "book"

    # ── Identidade ──────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ── Dados bibliográficos ─────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    author: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True, default="Português")

    # ── Estoque ──────────────────────────────────────────────────────────────
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Status / ciclo de vida ───────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        Enum(BookStatus, name="bookstatus"),
        default=BookStatus.DRAFT,
        nullable=False,
        index=True,
    )

    # ── Auditoria ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    trashed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Índices compostos ────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_book_status_title", "status", "title"),
    )

    # ── Métodos de ciclo de vida ─────────────────────────────────────────────
    def publish(self) -> None:
        """Promove o rascunho para ACTIVE."""
        self.status = BookStatus.ACTIVE
        self.updated_at = datetime.now(timezone.utc)

    def send_to_trash(self) -> None:
        """Soft-delete: move para TRASH."""
        self.status = BookStatus.TRASH
        self.trashed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restaura da lixeira para ACTIVE."""
        self.status = BookStatus.ACTIVE
        self.trashed_at = None
        self.updated_at = datetime.now(timezone.utc)

    # ── Propriedades auxiliares ──────────────────────────────────────────────
    @property
    def is_draft(self) -> bool:
        return self.status == BookStatus.DRAFT

    @property
    def is_active(self) -> bool:
        return self.status == BookStatus.ACTIVE

    @property
    def is_trashed(self) -> bool:
        return self.status == BookStatus.TRASH

    @property
    def is_available(self) -> bool:
        return self.is_active and self.available > 0

    # ── Serialização ─────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "isbn": self.isbn,
            "publisher": self.publisher,
            "year": self.year,
            "edition": self.edition,
            "genre": self.genre,
            "description": self.description,
            "cover_url": self.cover_url,
            "language": self.language,
            "quantity": self.quantity,
            "available": self.available,
            "status": self.status,
            "is_available": self.is_available,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "trashed_at": self.trashed_at.isoformat() if self.trashed_at else None,
        }

    def __repr__(self) -> str:
        return f"<Book id={self.id} title={self.title!r} status={self.status}>"
