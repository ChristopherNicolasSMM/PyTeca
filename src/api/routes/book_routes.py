from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from services.book_service import book_service
from model.book import BookStatus

book_api_bp = Blueprint("books_api", __name__, url_prefix="/api/books")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ok(data, code: int = 200):
    return jsonify({"success": True, "data": data}), code


def _err(message: str, code: int = 400):
    return jsonify({"success": False, "error": message}), code


def _book_or_404(book_id: int):
    book = book_service.get_by_id(book_id)
    if not book:
        return None, _err("Livro não encontrado.", 404)
    return book, None


# ── Listagem ──────────────────────────────────────────────────────────────────

@book_api_bp.route("/", methods=["GET"])
@login_required
def list_books():
    """
    GET /api/books/?status=active&search=...&genre=...&sort=title&dir=asc&page=1
    """
    status = request.args.get("status", BookStatus.ACTIVE)
    search = request.args.get("search", "").strip() or None
    genre = request.args.get("genre", "").strip() or None
    sort = request.args.get("sort", "title")
    direction = request.args.get("dir", "asc")
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 20))))

    result = book_service.list_books(
        page=page,
        per_page=per_page,
        status=status,
        search=search,
        genre=genre,
        sort=sort,
        direction=direction,
    )

    return _ok(
        {
            "items": [b.to_dict() for b in result.items],
            "total": result.total,
            "page": result.page,
            "per_page": result.per_page,
            "pages": result.pages,
        }
    )


@book_api_bp.route("/counts", methods=["GET"])
@login_required
def counts():
    """GET /api/books/counts — retorna contagem por status."""
    return _ok(book_service.count_by_status())


@book_api_bp.route("/genres", methods=["GET"])
@login_required
def genres():
    """GET /api/books/genres — lista gêneros cadastrados."""
    return _ok(book_service.get_genres())


# ── Detalhe ───────────────────────────────────────────────────────────────────

@book_api_bp.route("/<int:book_id>", methods=["GET"])
@login_required
def get_book(book_id: int):
    book, err = _book_or_404(book_id)
    if err:
        return err
    return _ok(book.to_dict())


# ── Criação direta (publicado) ────────────────────────────────────────────────

@book_api_bp.route("/", methods=["POST"])
@login_required
def create_book():
    """
    POST /api/books/
    Body JSON: { title, author, isbn?, publisher?, year?, edition?,
                 genre?, description?, cover_url?, language?,
                 quantity?, available? }
    """
    data = request.get_json(silent=True) or {}
    result = book_service.create(data)

    if not result.success:
        return _err(result.error, result.code)

    return _ok(result.data.to_dict(), 201)


# ── Draft ─────────────────────────────────────────────────────────────────────

@book_api_bp.route("/draft", methods=["POST"])
@login_required
def create_draft():
    """
    POST /api/books/draft
    Cria um rascunho vazio e retorna seu ID.
    Chamado pelo frontend ao abrir o formulário de novo livro.
    """
    result = book_service.create_draft()
    return _ok(result.data.to_dict(), 201)


@book_api_bp.route("/<int:book_id>/autosave", methods=["PATCH"])
@login_required
def autosave_draft(book_id: int):
    """
    PATCH /api/books/{id}/autosave
    Salva parcialmente um rascunho (auto-save).
    Aceita qualquer subconjunto de campos — não valida obrigatoriedade.
    """
    data = request.get_json(silent=True) or {}
    result = book_service.autosave_draft(book_id, data)

    if not result.success:
        return _err(result.error, result.code)

    return _ok({"id": result.data.id, "updated_at": result.data.updated_at.isoformat()})


@book_api_bp.route("/<int:book_id>/publish", methods=["POST"])
@login_required
def publish_draft(book_id: int):
    """
    POST /api/books/{id}/publish
    Finaliza o rascunho e publica.
    Body JSON opcional: campos finais a aplicar antes de publicar.
    """
    data = request.get_json(silent=True) or {}
    result = book_service.publish_draft(book_id, data or None)

    if not result.success:
        return _err(result.error, result.code)

    return _ok(result.data.to_dict())


@book_api_bp.route("/<int:book_id>/discard", methods=["DELETE"])
@login_required
def discard_draft(book_id: int):
    """
    DELETE /api/books/{id}/discard
    Descarta rascunho (exclusão imediata, sem lixeira).
    """
    result = book_service.discard_draft(book_id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data)


# ── Atualização ───────────────────────────────────────────────────────────────

@book_api_bp.route("/<int:book_id>", methods=["PUT", "PATCH"])
@login_required
def update_book(book_id: int):
    """
    PUT/PATCH /api/books/{id}
    Atualiza campos de um livro publicado ou rascunho.
    """
    data = request.get_json(silent=True) or {}
    result = book_service.update(book_id, data)

    if not result.success:
        return _err(result.error, result.code)

    return _ok(result.data.to_dict())


# ── Lixeira ───────────────────────────────────────────────────────────────────

@book_api_bp.route("/<int:book_id>/trash", methods=["POST"])
@login_required
def trash_book(book_id: int):
    """POST /api/books/{id}/trash — move para lixeira."""
    result = book_service.trash(book_id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict())


@book_api_bp.route("/<int:book_id>/restore", methods=["POST"])
@login_required
def restore_book(book_id: int):
    """POST /api/books/{id}/restore — restaura da lixeira."""
    result = book_service.restore(book_id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict())


@book_api_bp.route("/<int:book_id>", methods=["DELETE"])
@login_required
def delete_book(book_id: int):
    """
    DELETE /api/books/{id}
    Exclusão permanente — requer admin e livro na lixeira.
    """
    if not current_user.is_admin:
        return _err("Apenas administradores podem excluir permanentemente.", 403)

    result = book_service.delete_permanent(book_id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data)


# ── Estoque ───────────────────────────────────────────────────────────────────

@book_api_bp.route("/<int:book_id>/stock", methods=["PATCH"])
@login_required
def adjust_stock(book_id: int):
    """
    PATCH /api/books/{id}/stock
    Body: { "delta": <int> }  — positivo para adicionar, negativo para retirar.
    """
    data = request.get_json(silent=True) or {}
    delta = data.get("delta")

    if delta is None:
        return _err("Campo 'delta' é obrigatório.", 422)

    try:
        delta = int(delta)
    except (ValueError, TypeError):
        return _err("Campo 'delta' deve ser um número inteiro.", 422)

    result = book_service.adjust_stock(book_id, delta)
    if not result.success:
        return _err(result.error, result.code)

    return _ok({"id": book_id, "available": result.data.available, "quantity": result.data.quantity})
