from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from db.database import db
from model.bookstore.book import Book, BookStatus

logger = logging.getLogger(__name__)

# ── Campos de data do modelo (converter string → datetime) ────────────────────
_DATE_FIELDS: set[str] = set()
try:
    from sqlalchemy import DateTime, Date
    from sqlalchemy.orm import ColumnProperty
    for _prop in Book.__mapper__.iterate_properties:
        if isinstance(_prop, ColumnProperty):
            _col = _prop.columns[0]
            if isinstance(_col.type, (DateTime, Date)):
                _DATE_FIELDS.add(_prop.key)
except Exception:
    pass

# ── Campos só-leitura que nunca devem ser sobrescritos via form ───────────────
_READONLY = {"id", "status", "created_at", "updated_at", "trashed_at"}

# ── Colunas diretas ordenáveis (exclui relacionamentos/propriedades) ──────────
_SORTABLE: set[str] = set()
try:
    from sqlalchemy.orm import ColumnProperty as _CP
    for _prop in Book.__mapper__.iterate_properties:
        if isinstance(_prop, _CP):
            _SORTABLE.add(_prop.key)
except Exception:
    _SORTABLE = {"id"}


def _parse_date(value: Any) -> datetime | None:
    """Converte string de data para datetime. Aceita ISO, BR e datetime nativo."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    value = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
                "%d/%m/%Y", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Formato de data não reconhecido: '{value}'")


def _friendly_db_error(exc: Exception) -> str:
    """Converte IntegrityError do SQLAlchemy em mensagem amigável."""
    msg = str(exc)
    m = re.search(r"UNIQUE constraint failed:\s*\w+\.(\w+)", msg, re.IGNORECASE)
    if m:
        return f"Já existe um registro com este valor no campo '{m.group(1)}'. Verifique e tente novamente."
    m = re.search(r"NOT NULL constraint failed:\s*\w+\.(\w+)", msg, re.IGNORECASE)
    if m:
        field = m.group(1)
        # NOT NULL em UPDATE (book_id=NULL) significa que outro registro depende deste
        if "UPDATE" in msg.upper() or "update" in msg.lower():
            return (
                f"Não é possível excluir: outros registros dependem deste "
                f"(campo '{field}' em tabela relacionada). "
                f"Remova os registros dependentes primeiro."
            )
        return f"O campo '{field}' é obrigatório e não pode estar vazio."
    if "FOREIGN KEY" in msg.upper():
        return "Não é possível excluir: existem registros relacionados que dependem deste item."
    return f"Erro ao salvar: {msg.splitlines()[0][:200]}"


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
        extra_filters: dict | None = None,
    ) -> BookListResult:

        query = Book.query
        if status != "all":
            query = query.filter(Book.status == status)

        if search:
            pattern = f"%{search.strip()}%"
            from sqlalchemy import or_
            search_filters = []
            search_filters.append(Book.title.ilike(pattern))
            search_filters.append(Book.author.ilike(pattern))
            from model.bookstore.author import Author
            query = query.outerjoin(Author, Book.author_id == Author.id)
            search_filters.append(Author.name.ilike(pattern))
            if search_filters:
                query = query.filter(or_(*search_filters))

        # ── Filtros extras (@choices: genre, language, publisher, etc.) ───────
        for field, value in (extra_filters or {}).items():
            if value and hasattr(Book, field):
                col = getattr(Book, field)
                query = query.filter(col == value)

        # Ordena apenas por colunas diretas; ignora relacionamentos para evitar NotImplementedError
        if sort not in _SORTABLE:
            sort = "id"
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
        """Cria rascunho vazio. Falha graciosamente se houver colunas NOT NULL."""
        obj = Book(status=BookStatus.DRAFT)
        db.session.add(obj)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return ServiceResult(
                success=False,
                error="Este modelo possui campos obrigatórios. Use a criação direta (POST /).",
                code=400,
            )
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
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return ServiceResult(success=False, error=_friendly_db_error(e), code=422)
        return ServiceResult(success=True, data=obj)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create(self, data: dict) -> ServiceResult:
        obj = Book(status=BookStatus.ACTIVE)
        self._apply_fields(obj, data)
        db.session.add(obj)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning("Erro ao criar Book: %s", e)
            return ServiceResult(success=False, error=_friendly_db_error(e), code=422)
        return ServiceResult(success=True, data=obj, code=201)

    def update(self, id: int, data: dict) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Registro não encontrado.", code=404)
        if obj.status == BookStatus.TRASH:
            return ServiceResult(success=False, error="Não é possível editar um registro na lixeira.", code=400)
        self._apply_fields(obj, data)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning("Erro ao atualizar Book id=%s: %s", id, e)
            return ServiceResult(success=False, error=_friendly_db_error(e), code=422)
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
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning("Erro ao excluir Book id=%s: %s", id, e)
            return ServiceResult(success=False, error=_friendly_db_error(e), code=422)
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
        """
        Aplica campos do dict ao objeto ORM.
        - Ignora campos readonly (id, status, timestamps).
        - Converte strings de data para datetime automaticamente.
        - Converte campos FK (_id) e colunas Integer para tipos corretos.
        """
        from sqlalchemy import Integer
        from sqlalchemy.orm import ColumnProperty

        # Monta set de campos Integer do modelo para conversão automática
        _int_fields: set[str] = set()
        for _prop in obj.__class__.__mapper__.iterate_properties:
            if isinstance(_prop, ColumnProperty):
                if isinstance(_prop.columns[0].type, Integer):
                    _int_fields.add(_prop.key)

        for key, value in data.items():
            if key in _READONLY:
                continue
            if not hasattr(obj, key):
                continue

            # Conversão de datas
            if key in _DATE_FIELDS:
                try:
                    value = _parse_date(value)
                except ValueError as e:
                    if strict:
                        raise
                    logger.warning("Ignorando data inválida em '%s': %s", key, e)
                    continue

            # Conversão de inteiros (FKs e colunas Integer)
            if (key.endswith("_id") or key in _int_fields) and value is not None and value != "":
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    value = None

            setattr(obj, key, value)

        obj.updated_at = datetime.now(timezone.utc)
