from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from services.bookstore.loan_service import LoanService
from model.bookstore.loan import LoanStatus

loan_api_bp = Blueprint("loan_api", __name__, url_prefix="/api/loans")


def _ok(data, code: int = 200):
    return jsonify({"success": True, "data": data}), code


def _err(message: str, code: int = 400):
    return jsonify({"success": False, "error": message}), code


# ── Listagem ──────────────────────────────────────────────────────────────────

@loan_api_bp.route("/", methods=["GET"])
@login_required
def list():
    status = request.args.get("status", LoanStatus.ACTIVE.value)
    search = request.args.get("search", "").strip() or None
    sort = request.args.get("sort", "id")
    direction = request.args.get("dir", "asc")
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, int(request.args.get("per_page", 20)))

    service = LoanService()
    result = service.list(
        page=page, per_page=per_page, status=status,
        search=search, sort=sort, direction=direction,
    )
    return _ok({
        "items": [item.to_dict() for item in result.items],
        "total": result.total,
        "page": result.page,
        "per_page": result.per_page,
        "pages": result.pages,
    })


@loan_api_bp.route("/<int:id>", methods=["GET"])
@login_required
def get(id: int):
    service = LoanService()
    item = service.get_by_id(id)
    if not item:
        return _err("Não encontrado.", 404)
    return _ok(item.to_dict())


# ── Draft ─────────────────────────────────────────────────────────────────────

@loan_api_bp.route("/draft", methods=["POST"])
@login_required
def create_draft():
    service = LoanService()
    result = service.create_draft()
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict(), 201)


@loan_api_bp.route("/<int:id>/autosave", methods=["PATCH"])
@login_required
def autosave_draft(id: int):
    data = request.get_json(silent=True) or {}
    service = LoanService()
    result = service.autosave_draft(id, data)
    if not result.success:
        return _err(result.error, result.code)
    return _ok({"id": result.data.id, "updated_at": result.data.updated_at.isoformat()})


@loan_api_bp.route("/<int:id>/publish", methods=["POST"])
@login_required
def publish_draft(id: int):
    data = request.get_json(silent=True) or {}
    service = LoanService()
    result = service.publish_draft(id, data)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict())


# ── CRUD ──────────────────────────────────────────────────────────────────────

@loan_api_bp.route("/", methods=["POST"])
@login_required
def create():
    data = request.get_json(silent=True) or {}
    service = LoanService()
    result = service.create(data)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict(), 201)


@loan_api_bp.route("/<int:id>", methods=["PUT", "PATCH"])
@login_required
def update(id: int):
    data = request.get_json(silent=True) or {}
    service = LoanService()
    result = service.update(id, data)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict())


# ── Lixeira ───────────────────────────────────────────────────────────────────

@loan_api_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
def trash(id: int):
    service = LoanService()
    result = service.trash(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict())


@loan_api_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
def restore(id: int):
    service = LoanService()
    result = service.restore(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict())


@loan_api_bp.route("/<int:id>", methods=["DELETE"])
@login_required
def delete_permanent(id: int):
    if not current_user.is_admin:
        return _err("Apenas administradores podem excluir permanentemente.", 403)
    service = LoanService()
    result = service.delete_permanent(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data)


@loan_api_bp.route("/<int:id>/discard", methods=["DELETE"])
@login_required
def discard_draft(id: int):
    service = LoanService()
    result = service.discard_draft(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data)
