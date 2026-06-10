from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import db
from annotations import * # label, plural, listview, Column, Filter, form, Group, required, max_length, display_field

from model.bookstore.author import Author


class BookStatus(str, PyEnum):
    """Status do livro no ciclo de vida."""
    DRAFT = "draft"
    ACTIVE = "active"
    TRASH = "trash"


@label("Livros")
@plural("books")
@listview(
    columns=[
        Column("id", label="ID", width="60px", sortable=True),
        Column("title", label="Título", sortable=True, filterable=True),
        Column("author", label="Autor", sortable=True, filterable=True),
        Column("year", label="Ano", width="80px", align="center"),
        Column("available", label="Disponível", width="90px", align="center"),
        Column("status", label="Status", width="100px", align="center"),
    ],
    default_sort="title",
    filters=[
        Filter("search", type="text", placeholder="Título ou autor..."),
        Filter("genre", type="text", placeholder="Gênero"),
    ]
)
@form(
    fields=["title", "author_id", "isbn", "publisher", "year", "edition", "genre", "description", "cover_url", "language", "quantity", "available"],
    groups=[
        Group("basic", "Informações Básicas", ["title", "author_id", "isbn", "publisher", "year", "edition"]),
        Group("details", "Detalhes", ["genre", "description", "cover_url", "language"], collapsible=True),
        Group("stock", "Estoque", ["quantity", "available"], collapsible=True),
    ]
)
@display_field("title")
@required("title", "O título é obrigatório")
@required("author_id", "O autor é obrigatório")
class Book(db.Model):
    __tablename__ = "book"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), nullable=False)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True, default="Português")
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(Enum(BookStatus), default=BookStatus.DRAFT, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


    # Relacionamento
    author: Mapped["Author"] = relationship(back_populates="books")
     
    __table_args__ = (Index("ix_book_status_title", "status", "title"),)

    # Relacionamento com empréstimos (opcional, pode ser usado para navegação)
    loans: Mapped[list["Loan"]] = relationship(back_populates="book")

    def publish(self) -> None:
        self.status = BookStatus.ACTIVE
        self.updated_at = datetime.now(timezone.utc)

    def send_to_trash(self) -> None:
        self.status = BookStatus.TRASH
        self.trashed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        self.status = BookStatus.ACTIVE
        self.trashed_at = None
        self.updated_at = datetime.now(timezone.utc)

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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "author_id": self.author_id,
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
        return f"<Book id={self.id} title={self.title!r}>"
