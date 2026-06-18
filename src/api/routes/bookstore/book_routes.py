from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from services.bookstore.book_service import BookService
from model.bookstore.book import BookStatus

# ── Hooks de customização (pré/pós) ──────────────────────────────────────────
# book_routes_hooks.py é criado uma única vez pelo gerador
# e nunca sobrescrito depois — ver controller_hooks para o mesmo princípio.
def _noop(*args, **kwargs):
    return None

try:
    from api.routes.bookstore import book_routes_hooks as _hooks
except ImportError:
    _hooks = None

def _hook(name):
    return getattr(_hooks, name, _noop) if _hooks else _noop

book_api_bp = Blueprint("book_api", __name__, url_prefix="/api/bookstore/books")


def _ok(data, code: int = 200):
    return jsonify({"success": True, "data": data}), code


def _err(message: str, code: int = 400):
    return jsonify({"success": False, "error": message}), code


# ── Listagem ──────────────────────────────────────────────────────────────────

@book_api_bp.route("/", methods=["GET"])
@login_required
def list():
    early = _hook("pbo_list")(request)
    if early is not None:
        return early

    status = request.args.get("status", BookStatus.ACTIVE.value)
    search = request.args.get("search", "").strip() or None
    sort = request.args.get("sort", "id")
    direction = request.args.get("dir", "asc")
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, int(request.args.get("per_page", 20)))

    service = BookService()
    result = service.list(
        page=page, per_page=per_page, status=status,
        search=search, sort=sort, direction=direction,
    )
    payload = {
        "items": [item.to_dict() for item in result.items],
        "total": result.total,
        "page": result.page,
        "per_page": result.per_page,
        "pages": result.pages,
    }
    payload = _hook("pai_list")(payload, request) or payload
    return _ok(payload)


@book_api_bp.route("/<int:id>", methods=["GET"])
@login_required
def get(id: int):
    service = BookService()
    item = service.get_by_id(id)
    if not item:
        return _err("Não encontrado.", 404)
    return _ok(item.to_dict())


# ── Draft ─────────────────────────────────────────────────────────────────────

@book_api_bp.route("/draft", methods=["POST"])
@login_required
def create_draft():
    service = BookService()
    result = service.create_draft()
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict(), 201)


@book_api_bp.route("/<int:id>/autosave", methods=["PATCH"])
@login_required
def autosave_draft(id: int):
    data = request.get_json(silent=True) or {}
    service = BookService()
    result = service.autosave_draft(id, data)
    if not result.success:
        return _err(result.error, result.code)
    return _ok({"id": result.data.id, "updated_at": result.data.updated_at.isoformat()})


@book_api_bp.route("/<int:id>/publish", methods=["POST"])
@login_required
def publish_draft(id: int):
    data = request.get_json(silent=True) or {}
    service = BookService()
    result = service.publish_draft(id, data)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict())


# ── CRUD ──────────────────────────────────────────────────────────────────────

@book_api_bp.route("/", methods=["POST"])
@login_required
def create():
    data = request.get_json(silent=True) or {}
    data = _hook("pbo_create")(data, request) or data

    service = BookService()
    result = service.create(data)
    if not result.success:
        return _err(result.error, result.code)

    _hook("pai_create")(result.data, request)
    return _ok(result.data.to_dict(), 201)


@book_api_bp.route("/<int:id>", methods=["PUT", "PATCH"])
@login_required
def update(id: int):
    data = request.get_json(silent=True) or {}
    data = _hook("pbo_update")(id, data, request) or data

    service = BookService()
    result = service.update(id, data)
    if not result.success:
        return _err(result.error, result.code)

    _hook("pai_update")(result.data, request)
    return _ok(result.data.to_dict())


# ── Lixeira ───────────────────────────────────────────────────────────────────

@book_api_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
def trash(id: int):
    service = BookService()
    obj = service.get_by_id(id)

    early = _hook("pbo_delete")(id, "trash", request)
    if early is not None:
        return early

    result = service.trash(id)
    if not result.success:
        return _err(result.error, result.code)

    _hook("pai_delete")(id, "trash", result, request)
    return _ok(result.data.to_dict())


@book_api_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
def restore(id: int):
    service = BookService()
    result = service.restore(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict())


@book_api_bp.route("/<int:id>", methods=["DELETE"])
@login_required
def delete_permanent(id: int):
    if not current_user.is_admin:
        return _err("Apenas administradores podem excluir permanentemente.", 403)

    service = BookService()
    obj = service.get_by_id(id)

    early = _hook("pbo_delete")(id, "delete_permanent", request)
    if early is not None:
        return early

    result = service.delete_permanent(id)
    if not result.success:
        return _err(result.error, result.code)

    _hook("pai_delete")(id, "delete_permanent", result, request)
    return _ok(result.data)


@book_api_bp.route("/<int:id>/discard", methods=["DELETE"])
@login_required
def discard_draft(id: int):
    service = BookService()
    result = service.discard_draft(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data)
