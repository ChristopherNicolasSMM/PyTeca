# model/loan.py
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import ForeignKey, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import db
from annotations import label, plural, listview, Column, Filter, form, Group, required
from model.core.user import User
from model.bookstore.book import Book

class LoanStatus(str, PyEnum):
    ACTIVE = "active"
    RETURNED = "returned"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

@label("Empréstimos")
@plural("loans")
@listview(
    columns=[
        Column("id", label="ID", width="60px", sortable=True),
        Column("user.username", label="Usuário", sortable=True, filterable=True),
        Column("book.title", label="Livro", sortable=True, filterable=True),
        Column("loan_date", label="Data Empréstimo", width="120px", align="center"),
        Column("due_date", label="Data Devolução", width="120px", align="center"),
        Column("status", label="Status", width="100px", align="center"),
    ],
    default_sort="-loan_date",
    filters=[
        Filter("status", type="select", options=[(s.value, s.name.capitalize()) for s in LoanStatus]),
        Filter("search", type="text", placeholder="Usuário ou livro..."),
    ]
)
@form(
    fields=["user_id", "book_id", "loan_date", "due_date", "status", "notes"],
    groups=[
        Group("basic", "Dados do Empréstimo", ["user_id", "book_id", "loan_date", "due_date"]),
        Group("status", "Situação", ["status"]),
        Group("notes", "Observações", ["notes"], collapsible=True),
    ]
)
@required("user_id", "Usuário é obrigatório")
@required("book_id", "Livro é obrigatório")
@required("loan_date", "Data do empréstimo é obrigatória")
@required("due_date", "Data de devolução é obrigatória")
class Loan(db.Model):
    __tablename__ = "loans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    book_id: Mapped[int] = mapped_column(ForeignKey("book.id"), nullable=False)
    loan_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    return_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=LoanStatus.ACTIVE, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(backref="loans")
    book: Mapped["Book"] = relationship(back_populates="loans")

    @property
    def is_active(self) -> bool:
        return self.status == LoanStatus.ACTIVE

    @property
    def is_returned(self) -> bool:
        return self.status == LoanStatus.RETURNED

    @property
    def is_overdue(self) -> bool:
        return self.status == LoanStatus.OVERDUE

    def mark_returned(self) -> None:
        self.status = LoanStatus.RETURNED
        self.return_date = datetime.now(timezone.utc)

    def mark_overdue(self) -> None:
        if self.status == LoanStatus.ACTIVE:
            self.status = LoanStatus.OVERDUE

    def cancel(self) -> None:
        self.status = LoanStatus.CANCELLED

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "book_id": self.book_id,
            "user_name": self.user.username if self.user else None,
            "book_title": self.book.title if self.book else None,
            "loan_date": self.loan_date.isoformat() if self.loan_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "return_date": self.return_date.isoformat() if self.return_date else None,
            "status": self.status,
            "notes": self.notes,
            "is_active": self.is_active,
            "is_returned": self.is_returned,
            "is_overdue": self.is_overdue,
        }

    def __repr__(self):
        return f"<Loan id={self.id} user_id={self.user_id} book_id={self.book_id} status={self.status}>"