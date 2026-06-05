from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from model.core.user_layout_pref import UserLayoutPref

smart_list_api_bp = Blueprint("smart_list_api", __name__, url_prefix="/api/layout")


def _ok(data=None, code: int = 200):
    return jsonify({"success": True, "data": data or {}}), code


def _err(msg: str, code: int = 400):
    return jsonify({"success": False, "error": msg}), code


@smart_list_api_bp.route("/save", methods=["POST"])
@login_required
def save_layout():
    """
    POST /api/layout/save
    Body: {
        "list_id": "books",
        "columns": ["title", "author", "isbn"],
        "hidden": ["isbn"],
        "per_page": 20,
        "visible_to_all": false
    }
    """
    data = request.get_json(silent=True) or {}
    list_id = data.get("list_id", "").strip()

    if not list_id:
        return _err("list_id é obrigatório.")

    layout = {
        "columns": data.get("columns", []),
        "hidden": data.get("hidden", []),
        "per_page": int(data.get("per_page", 20)),
    }

    pref = UserLayoutPref.save_for_user(current_user.id, list_id, layout)

    if data.get("visible_to_all"):
        pref.visible_to_all = True
        from db.database import db
        db.session.commit()

    return _ok({"list_id": list_id, "saved": True})


@smart_list_api_bp.route("/<list_id>", methods=["GET"])
@login_required
def get_layout(list_id: str):
    """GET /api/layout/<list_id> — retorna layout salvo do usuário."""
    pref = UserLayoutPref.get_for_user(current_user.id, list_id)
    if not pref:
        return _ok(None)
    return _ok(pref.layout)


@smart_list_api_bp.route("/<list_id>/reset", methods=["DELETE"])
@login_required
def reset_layout(list_id: str):
    """DELETE /api/layout/<list_id>/reset — volta ao layout padrão."""
    deleted = UserLayoutPref.delete_for_user(current_user.id, list_id)
    return _ok({"deleted": deleted})
