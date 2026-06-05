from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func

from db.database import db
from model.book import Book, BookStatus


@dataclass
class BookListResult:
    items: list[Book]
    total: int
    page: int
    per_page: int
    pages: int


@dataclass
class ServiceResult:
    success: bool
    data: Any = None
    error: str | None = None
    code: int = 200


class BookService:
    """Camada de negócio para Livros."""

    # ── Listagem ──────────────────────────────────────────────────────────────

    def list(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        status: str = BookStatus.ACTIVE,
        search: str | None = None,
        sort: str = "id",
        direction: str = "asc",
    ) -> BookListResult:
        query = Book.query
        if status != "all":
            query = query.filter(Book.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(Book.name.ilike(pattern))
        sort_col = getattr(Book, sort, Book.id)
        query = query.order_by(sort_col.desc() if direction == "desc" else sort_col.asc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return BookListResult(
            items=pagination.items,
            total=pagination.total,
            page=page,
            per_page=per_page,
            pages=pagination.pages,
        )

    def get_by_id(self, id: int) -> Book | None:
        return db.session.get(Book, id)

    def count_by_status(self) -> dict[str, int]:
        rows = (
            db.session.query(Book.status, func.count(Book.id))
            .group_by(Book.status)
            .all()
        )
        result = {s.value: 0 for s in BookStatus}
        for status, count in rows:
            result[status] = count
        return result

    # ── Draft ─────────────────────────────────────────────────────────────────

    def create_draft(self) -> ServiceResult:
        obj = Book(status=BookStatus.DRAFT)
        db.session.add(obj)
        db.session.commit()
        return ServiceResult(success=True, data=obj, code=201)

    def autosave_draft(self, id: int, data: dict) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Não encontrado.", code=404)
        if obj.status != BookStatus.DRAFT:
            return ServiceResult(success=False, error="Auto-save só é permitido em rascunhos.", code=400)
        self._apply_fields(obj, data, strict=False)
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def publish_draft(self, id: int, data: dict | None = None) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj or obj.status != BookStatus.DRAFT:
            return ServiceResult(success=False, error="Rascunho não encontrado.", code=404)
        if data:
            self._apply_fields(obj, data)
        obj.status = BookStatus.ACTIVE
        obj.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create(self, data: dict) -> ServiceResult:
        obj = Book(status=BookStatus.ACTIVE)
        self._apply_fields(obj, data)
        db.session.add(obj)
        db.session.commit()
        return ServiceResult(success=True, data=obj, code=201)

    def update(self, id: int, data: dict) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Registro não encontrado.", code=404)
        if obj.status == BookStatus.TRASH:
            return ServiceResult(success=False, error="Não é possível editar um registro na lixeira.", code=400)
        self._apply_fields(obj, data)
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def trash(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Não encontrado.", code=404)
        if obj.status == BookStatus.TRASH:
            return ServiceResult(success=False, error="Já está na lixeira.", code=400)
        obj.status = BookStatus.TRASH
        obj.trashed_at = datetime.now(timezone.utc)
        obj.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def restore(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Não encontrado.", code=404)
        if obj.status != BookStatus.TRASH:
            return ServiceResult(success=False, error="Não está na lixeira.", code=400)
        obj.status = BookStatus.ACTIVE
        obj.trashed_at = None
        obj.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def delete_permanent(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Não encontrado.", code=404)
        if obj.status != BookStatus.TRASH:
            return ServiceResult(
                success=False,
                error="Apenas registros na lixeira podem ser excluídos permanentemente.",
                code=400,
            )
        db.session.delete(obj)
        db.session.commit()
        return ServiceResult(success=True, data={"id": id})

    def discard_draft(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Rascunho não encontrado.", code=404)
        if obj.status != BookStatus.DRAFT:
            return ServiceResult(success=False, error="Apenas rascunhos podem ser descartados.", code=400)
        db.session.delete(obj)
        db.session.commit()
        return ServiceResult(success=True, data={"id": id})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _apply_fields(self, obj: Book, data: dict, strict: bool = True) -> None:
        """Aplica campos do dict ao objeto ORM. Sobrescreva para validação customizada."""
        for key, value in data.items():
            if key in ("id", "status", "created_at", "updated_at", "trashed_at"):
                continue
            if hasattr(obj, key):
                setattr(obj, key, value)
        obj.updated_at = datetime.now(timezone.utc)
