from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func

from db.database import db
from model.author import Author, AuthorStatus


@dataclass
class AuthorListResult:
    items: list[Author]
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


class AuthorService:
    """Camada de negócio para author."""

    def list(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        status: str = AuthorStatus.ACTIVE,
        search: str | None = None,
        genre: str | None = None,
        sort: str = "id",
        direction: str = "asc",
    ) -> AuthorListResult:
        query = Author.query
        if status != "all":
            query = query.filter(Author.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(Author.name.ilike(pattern))
        if genre:
            query = query.filter(Author.genre.ilike(f"%{genre}%"))
        sort_col = getattr(Author, sort, Author.id)
        query = query.order_by(sort_col.desc() if direction == "desc" else sort_col.asc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return AuthorListResult(
            items=pagination.items,
            total=pagination.total,
            page=page,
            per_page=per_page,
            pages=pagination.pages,
        )

    def get_by_id(self, id: int) -> Author | None:
        return db.session.get(Author, id)

    def create_draft(self) -> ServiceResult:
        obj = Author(status=AuthorStatus.DRAFT)
        db.session.add(obj)
        db.session.commit()
        return ServiceResult(success=True, data=obj, code=201)

    def publish_draft(self, id: int, data: dict | None = None) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj or obj.status != AuthorStatus.DRAFT:
            return ServiceResult(success=False, error="Rascunho não encontrado", code=404)
        if data:
            self._apply_fields(obj, data)
        obj.status = AuthorStatus.ACTIVE
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def update(self, id: int, data: dict) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Registro não encontrado", code=404)
        self._apply_fields(obj, data)
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def trash(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Registro não encontrado", code=404)
        obj.status = AuthorStatus.TRASH
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def restore(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj or obj.status != AuthorStatus.TRASH:
            return ServiceResult(success=False, error="Registro não está na lixeira", code=404)
        obj.status = AuthorStatus.ACTIVE
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def delete_permanent(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj or obj.status != AuthorStatus.TRASH:
            return ServiceResult(success=False, error="Apenas registros na lixeira podem ser excluídos", code=400)
        db.session.delete(obj)
        db.session.commit()
        return ServiceResult(success=True, data={"id": id})

    def discard_draft(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj or obj.status != AuthorStatus.DRAFT:
            return ServiceResult(success=False, error="Apenas rascunhos podem ser descartados", code=400)
        db.session.delete(obj)
        db.session.commit()
        return ServiceResult(success=True, data={"id": id})

    def _apply_fields(self, obj: Author, data: dict) -> None:
        for key, value in data.items():
            if hasattr(obj, key) and value is not None:
                setattr(obj, key, value)
