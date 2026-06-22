from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from utils.permissions import permission_required
from services.core.admin.snapshot_service import SnapshotService

snapshots_api_bp = Blueprint("snapshots_api", __name__, url_prefix="/api/admin/snapshots")


def _ok(data=None, code=200):
    return jsonify({"success": True, **(data or {})}), code


def _err(message, code=400):
    return jsonify({"success": False, "error": message}), code


@snapshots_api_bp.route("/files", methods=["GET"])
@login_required
@permission_required("admin")
def list_files():
    """Lista arquivos com histórico de versionamento (para a lista lateral)."""
    search = request.args.get("search", "").strip() or None
    files = SnapshotService.list_files(search=search)
    return _ok({"files": files})


@snapshots_api_bp.route("/history", methods=["GET"])
@login_required
@permission_required("admin")
def get_history():
    """Histórico de um arquivo específico — ?file_path=controller/bookstore/book.py"""
    file_path = request.args.get("file_path", "").strip()
    if not file_path:
        return _err("Parâmetro 'file_path' é obrigatório.")
    history = SnapshotService.get_history(file_path)
    return _ok({"file_path": file_path, "history": history})


@snapshots_api_bp.route("/<int:snapshot_id>", methods=["GET"])
@login_required
@permission_required("admin")
def get_snapshot(snapshot_id: int):
    """Conteúdo completo de um snapshot isolado (preview de uma única versão)."""
    data = SnapshotService.get_content(snapshot_id)
    if data is None:
        return _err("Snapshot não encontrado.", 404)
    return _ok({"snapshot": data})


@snapshots_api_bp.route("/diff", methods=["GET"])
@login_required
@permission_required("admin")
def diff():
    """Diff entre duas versões — ?a=<id>&b=<id>"""
    try:
        snapshot_a = int(request.args.get("a", ""))
        snapshot_b = int(request.args.get("b", ""))
    except (TypeError, ValueError):
        return _err("Parâmetros 'a' e 'b' (IDs de snapshot) são obrigatórios.")

    result = SnapshotService.diff(snapshot_a, snapshot_b)
    if result is None:
        return _err("Snapshots não encontrados ou pertencem a arquivos diferentes.", 404)
    return _ok({"diff": result})


@snapshots_api_bp.route("/<int:snapshot_id>/restore", methods=["POST"])
@login_required
@permission_required("admin")
def restore(snapshot_id: int):
    """
    Restaura uma versão antiga, escrevendo-a de volta no arquivo real e
    criando um novo snapshot (origin=restore) — nunca silenciosamente.
    """
    result = SnapshotService.restore(snapshot_id, created_by_user_id=current_user.id)
    if not result.get("success"):
        return _err(result.get("error", "Falha ao restaurar."), 422)
    return _ok(result)
