from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func

from db.database import db
from model.book import Book, BookStatus


# ── DTOs de resultado ─────────────────────────────────────────────────────────

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


# ── Serviço ───────────────────────────────────────────────────────────────────

class BookService:
    """
    Camada de negócio para livros.

    Responsabilidades:
    - CRUD completo (create, read, update, delete/trash/restore)
    - Gerenciamento de rascunhos (draft + auto-save)
    - Listagem paginada com filtros por status, título, autor, gênero
    - Validações de negócio (ISBN duplicado, estoque, etc.)
    """

    # ── Listagem e busca ──────────────────────────────────────────────────────

    def list_books(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        status: str = BookStatus.ACTIVE,
        search: str | None = None,
        genre: str | None = None,
        sort: str = "title",
        direction: str = "asc",
    ) -> BookListResult:
        """
        Retorna livros paginados com filtros opcionais.

        Args:
            status: 'active' | 'draft' | 'trash' | 'all'
        """
        query = Book.query

        # Filtro de status
        if status != "all":
            query = query.filter(Book.status == status)

        # Busca textual (título ou autor)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                (Book.title.ilike(pattern)) | (Book.author.ilike(pattern))
            )

        # Filtro de gênero
        if genre:
            query = query.filter(Book.genre.ilike(f"%{genre}%"))

        # Ordenação
        sort_col = {
            "title": Book.title,
            "author": Book.author,
            "year": Book.year,
            "created_at": Book.created_at,
            "updated_at": Book.updated_at,
        }.get(sort, Book.title)

        query = query.order_by(
            sort_col.desc() if direction == "desc" else sort_col.asc()
        )

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return BookListResult(
            items=pagination.items,
            total=pagination.total,
            page=page,
            per_page=per_page,
            pages=pagination.pages,
        )

    def get_by_id(self, book_id: int) -> Book | None:
        return db.session.get(Book, book_id)

    def get_by_isbn(self, isbn: str) -> Book | None:
        return Book.query.filter_by(isbn=isbn).first()

    def get_genres(self) -> list[str]:
        """Retorna lista de gêneros únicos (apenas livros ativos)."""
        rows = (
            db.session.query(Book.genre)
            .filter(Book.status == BookStatus.ACTIVE, Book.genre.isnot(None))
            .distinct()
            .order_by(Book.genre)
            .all()
        )
        return [r.genre for r in rows]

    def count_by_status(self) -> dict[str, int]:
        """Retorna contagem agrupada por status (útil para badges na UI)."""
        rows = (
            db.session.query(Book.status, func.count(Book.id))
            .group_by(Book.status)
            .all()
        )
        result = {s.value: 0 for s in BookStatus}
        for status, count in rows:
            result[status] = count
        return result

    # ── Draft (rascunho) ──────────────────────────────────────────────────────

    def create_draft(self) -> ServiceResult:
        """
        Cria um rascunho vazio imediatamente ao abrir o formulário.
        O ID é retornado para que o frontend faça auto-save nele.
        """
        book = Book(
            title="",
            author="",
            status=BookStatus.DRAFT,
        )
        db.session.add(book)
        db.session.commit()
        return ServiceResult(success=True, data=book, code=201)

    def autosave_draft(self, book_id: int, data: dict) -> ServiceResult:
        """
        Salva parcialmente um rascunho (auto-save enquanto o usuário digita).
        Não valida campos obrigatórios — aceita dados incompletos.
        """
        book = self.get_by_id(book_id)
        if not book:
            return ServiceResult(success=False, error="Livro não encontrado.", code=404)

        if book.status != BookStatus.DRAFT:
            return ServiceResult(
                success=False,
                error="Auto-save só é permitido em rascunhos.",
                code=400,
            )

        _apply_fields(book, data, strict=False)
        db.session.commit()
        return ServiceResult(success=True, data=book)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create(self, data: dict) -> ServiceResult:
        """
        Cria e publica um livro diretamente (sem passar por draft).
        Valida campos obrigatórios e ISBN único.
        """
        validation = _validate(data)
        if validation:
            return ServiceResult(success=False, error=validation, code=422)

        if data.get("isbn"):
            existing = self.get_by_isbn(data["isbn"])
            if existing:
                return ServiceResult(
                    success=False,
                    error=f"ISBN {data['isbn']} já cadastrado (id={existing.id}).",
                    code=409,
                )

        book = Book(status=BookStatus.ACTIVE)
        _apply_fields(book, data)
        db.session.add(book)
        db.session.commit()
        return ServiceResult(success=True, data=book, code=201)

    def publish_draft(self, book_id: int, data: dict | None = None) -> ServiceResult:
        """
        Finaliza um rascunho: aplica dados finais (se fornecidos) e publica.
        """
        book = self.get_by_id(book_id)
        if not book:
            return ServiceResult(success=False, error="Livro não encontrado.", code=404)

        if book.status != BookStatus.DRAFT:
            return ServiceResult(
                success=False, error="Livro não é um rascunho.", code=400
            )

        if data:
            _apply_fields(book, data)

        # Valida antes de publicar
        validation = _validate(book.__dict__)
        if validation:
            return ServiceResult(success=False, error=validation, code=422)

        if book.isbn:
            duplicate = Book.query.filter(
                Book.isbn == book.isbn, Book.id != book.id
            ).first()
            if duplicate:
                return ServiceResult(
                    success=False,
                    error=f"ISBN {book.isbn} já cadastrado em outro livro.",
                    code=409,
                )

        book.publish()
        db.session.commit()
        return ServiceResult(success=True, data=book)

    def update(self, book_id: int, data: dict) -> ServiceResult:
        """Atualiza um livro existente (ACTIVE ou DRAFT)."""
        book = self.get_by_id(book_id)
        if not book:
            return ServiceResult(success=False, error="Livro não encontrado.", code=404)

        if book.is_trashed:
            return ServiceResult(
                success=False,
                error="Não é possível editar um livro na lixeira. Restaure-o primeiro.",
                code=400,
            )

        if data.get("isbn") and data["isbn"] != book.isbn:
            duplicate = Book.query.filter(
                Book.isbn == data["isbn"], Book.id != book_id
            ).first()
            if duplicate:
                return ServiceResult(
                    success=False,
                    error=f"ISBN {data['isbn']} já cadastrado em outro livro.",
                    code=409,
                )

        _apply_fields(book, data)
        db.session.commit()
        return ServiceResult(success=True, data=book)

    def trash(self, book_id: int) -> ServiceResult:
        """Move o livro para a lixeira (soft-delete)."""
        book = self.get_by_id(book_id)
        if not book:
            return ServiceResult(success=False, error="Livro não encontrado.", code=404)

        if book.is_trashed:
            return ServiceResult(
                success=False, error="Livro já está na lixeira.", code=400
            )

        book.send_to_trash()
        db.session.commit()
        return ServiceResult(success=True, data=book)

    def restore(self, book_id: int) -> ServiceResult:
        """Restaura um livro da lixeira para ACTIVE."""
        book = self.get_by_id(book_id)
        if not book:
            return ServiceResult(success=False, error="Livro não encontrado.", code=404)

        if not book.is_trashed:
            return ServiceResult(
                success=False, error="Livro não está na lixeira.", code=400
            )

        book.restore()
        db.session.commit()
        return ServiceResult(success=True, data=book)

    def delete_permanent(self, book_id: int) -> ServiceResult:
        """
        Exclusão permanente — somente para livros já na lixeira.
        Requer permissão de admin (verificar no controller/route).
        """
        book = self.get_by_id(book_id)
        if not book:
            return ServiceResult(success=False, error="Livro não encontrado.", code=404)

        if not book.is_trashed:
            return ServiceResult(
                success=False,
                error="Apenas livros na lixeira podem ser excluídos permanentemente.",
                code=400,
            )

        db.session.delete(book)
        db.session.commit()
        return ServiceResult(success=True, data={"id": book_id})

    def discard_draft(self, book_id: int) -> ServiceResult:
        """
        Descarta um rascunho — exclusão imediata (rascunhos não vão para lixeira).
        """
        book = self.get_by_id(book_id)
        if not book:
            return ServiceResult(success=False, error="Rascunho não encontrado.", code=404)

        if book.status != BookStatus.DRAFT:
            return ServiceResult(
                success=False,
                error="Apenas rascunhos podem ser descartados. Use trash() para livros publicados.",
                code=400,
            )

        db.session.delete(book)
        db.session.commit()
        return ServiceResult(success=True, data={"id": book_id})

    # ── Estoque ───────────────────────────────────────────────────────────────

    def adjust_stock(self, book_id: int, delta: int) -> ServiceResult:
        """
        Ajusta o estoque disponível em `delta` unidades (+/-).
        Garante que `available` não fique negativo nem supere `quantity`.
        """
        book = self.get_by_id(book_id)
        if not book:
            return ServiceResult(success=False, error="Livro não encontrado.", code=404)

        new_available = book.available + delta
        if new_available < 0:
            return ServiceResult(
                success=False, error="Estoque disponível não pode ser negativo.", code=422
            )
        if new_available > book.quantity:
            return ServiceResult(
                success=False,
                error=f"Disponível ({new_available}) não pode superar quantidade total ({book.quantity}).",
                code=422,
            )

        book.available = new_available
        book.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return ServiceResult(success=True, data=book)


# ── Funções auxiliares (privadas) ─────────────────────────────────────────────

def _apply_fields(book: Book, data: dict, strict: bool = True) -> None:
    """Aplica campos do dicionário ao objeto Book."""
    string_fields = [
        "title", "author", "isbn", "publisher", "edition",
        "genre", "description", "cover_url", "language",
    ]
    int_fields = ["year", "quantity", "available"]

    for f in string_fields:
        if f in data:
            value = data[f]
            setattr(book, f, value.strip() if isinstance(value, str) else value)

    for f in int_fields:
        if f in data:
            try:
                setattr(book, f, int(data[f]) if data[f] not in (None, "") else None)
            except (ValueError, TypeError):
                if strict:
                    raise ValueError(f"Campo '{f}' deve ser numérico.")


def _validate(data: dict) -> str | None:
    """Retorna mensagem de erro se inválido, None se ok."""
    title = (data.get("title") or "").strip()
    author = (data.get("author") or "").strip()

    if not title:
        return "O título é obrigatório."
    if not author:
        return "O autor é obrigatório."

    return None


# ── Instância singleton para importação direta ────────────────────────────────
book_service = BookService()
