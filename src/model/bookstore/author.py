# model/author.py
from __future__ import annotations
from enum import Enum as PyEnum

from annotations import * # label, plural, listview, Column, Filter, form, Group, required, max_length, display_field
from db.database import db

from sqlalchemy import ForeignKey, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship


class AuthorStatus(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    TRASH = "trash"


@label("Autores")
@plural("authors")
@listview(
    columns=[
        Column("id", label="ID", width="60px", sortable=True),
        Column("name", label="Nome", sortable=True, filterable=True),
        Column("birth_year", label="Ano Nascimento", width="100px", align="center"),
    ],
    default_sort="name",
    filters=[
        Filter("name", type="text", placeholder="Buscar por nome..."),
    ]
)
@form(
    fields=["name", "birth_year", "bio"],
    groups=[
        Group("basic", "Informações Básicas", ["name", "birth_year"]),
        Group("bio", "Biografia", ["bio"], collapsible=True),
    ]
)
@required("name", "Nome do autor é obrigatório")
@max_length("name", 100)
class Author(db.Model):
    __tablename__ = "authors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, default="")
    birth_year = db.Column(db.Integer)
    bio = db.Column(db.Text)
    status = db.Column(db.String(20), default=AuthorStatus.DRAFT, nullable=False)
    
    # Relacionamento com livros (opcional, pode ser usado para navegação)
    books: Mapped[list["Book"]] = relationship(back_populates="author")

    def publish(self) -> None:
        """Muda o status para ACTIVE."""
        self.status = AuthorStatus.ACTIVE

    def send_to_trash(self) -> None:
        """Muda o status para TRASH."""
        self.status = AuthorStatus.TRASH

    def restore(self) -> None:
        """Restaura da lixeira para ACTIVE."""
        self.status = AuthorStatus.ACTIVE

    @property
    def is_draft(self) -> bool:
        return self.status == AuthorStatus.DRAFT

    @property
    def is_active(self) -> bool:
        return self.status == AuthorStatus.ACTIVE

    @property
    def is_trashed(self) -> bool:
        return self.status == AuthorStatus.TRASH

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "birth_year": self.birth_year,
            "bio": self.bio,
            "status": self.status,
            "is_draft": self.is_draft,
            "is_active": self.is_active,
            "is_trashed": self.is_trashed,
        }

    def __repr__(self):
        return f"<Author {self.name}>"