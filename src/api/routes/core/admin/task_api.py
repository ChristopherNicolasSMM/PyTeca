"""
task_api.py — API REST para tarefas agendadas, fila e logs.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from services.core.admin.task_service import TaskService
from utils.permissions import permission_required

task_api_bp = Blueprint("task_api", __name__, url_prefix="/api/admin/tasks")


def _ok(data=None, code=200):
    return jsonify({"success": True, "data": data or {}}), code


def _err(msg: str, code=400):
    return jsonify({"success": False, "error": msg}), code


# ── Dashboard ────────────────────────────────────────────────────────────────

@task_api_bp.route("/stats", methods=["GET"])
@login_required
@permission_required("admin")
def stats():
    return _ok(TaskService.recent_stats())


# ── Tarefas ──────────────────────────────────────────────────────────────────

@task_api_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def list_tasks():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status   = request.args.get("status") or None
    return _ok(TaskService.list_tasks(page=page, per_page=per_page, status=status))


@task_api_bp.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create_task():
    data = request.get_json(silent=True) or {}
    data["created_by"] = current_user.id
    result = TaskService.create_task(data)
    if not result["success"]:
        return _err(result["error"])
    return _ok(result["data"], 201)


@task_api_bp.route("/<int:task_id>", methods=["GET"])
@login_required
@permission_required("admin")
def get_task(task_id: int):
    task = TaskService.get_task(task_id)
    if not task:
        return _err("Tarefa não encontrada.", 404)
    return _ok(TaskService._task_to_dict(task))


@task_api_bp.route("/<int:task_id>", methods=["PUT", "PATCH"])
@login_required
@permission_required("admin")
def update_task(task_id: int):
    data   = request.get_json(silent=True) or {}
    result = TaskService.update_task(task_id, data)
    if not result["success"]:
        return _err(result["error"])
    return _ok(result["data"])


@task_api_bp.route("/<int:task_id>", methods=["DELETE"])
@login_required
@permission_required("admin")
def delete_task(task_id: int):
    result = TaskService.delete_task(task_id)
    if not result["success"]:
        return _err(result["error"])
    return _ok()


@task_api_bp.route("/<int:task_id>/run", methods=["POST"])
@login_required
@permission_required("admin")
def run_now(task_id: int):
    result = TaskService.run_now(task_id)
    if not result["success"]:
        return _err(result.get("error", "Falha na execução."))
    return _ok(result)


@task_api_bp.route("/<int:task_id>/pause", methods=["POST"])
@login_required
@permission_required("admin")
def pause_task(task_id: int):
    result = TaskService.pause_task(task_id)
    if not result["success"]:
        return _err(result["error"])
    return _ok(result["data"])


@task_api_bp.route("/<int:task_id>/activate", methods=["POST"])
@login_required
@permission_required("admin")
def activate_task(task_id: int):
    result = TaskService.activate_task(task_id)
    if not result["success"]:
        return _err(result["error"])
    return _ok(result["data"])


@task_api_bp.route("/<int:task_id>/approve", methods=["POST"])
@login_required
@permission_required("admin")
def approve_task(task_id: int):
    result = TaskService.approve_task(task_id)
    if not result["success"]:
        return _err(result["error"])
    return _ok(result["data"])


# ── Logs ─────────────────────────────────────────────────────────────────────

@task_api_bp.route("/<int:task_id>/logs", methods=["GET"])
@login_required
@permission_required("admin")
def task_logs(task_id: int):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    return _ok(TaskService.list_logs(task_id=task_id, page=page, per_page=per_page))


@task_api_bp.route("/logs", methods=["GET"])
@login_required
@permission_required("admin")
def all_logs():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    return _ok(TaskService.list_logs(page=page, per_page=per_page))


# ── Fila ─────────────────────────────────────────────────────────────────────

@task_api_bp.route("/queue", methods=["GET"])
@login_required
@permission_required("admin")
def list_queue():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status   = request.args.get("status") or None
    return _ok(TaskService.list_queue(page=page, per_page=per_page, status=status))


@task_api_bp.route("/queue/<int:msg_id>/reprocess", methods=["POST"])
@login_required
@permission_required("admin")
def reprocess(msg_id: int):
    result = TaskService.reprocess_message(msg_id)
    if not result["success"]:
        return _err(result["error"])
    return _ok()


@task_api_bp.route("/queue/<int:msg_id>/cancel", methods=["POST"])
@login_required
@permission_required("admin")
def cancel_message(msg_id: int):
    result = TaskService.cancel_message(msg_id)
    if not result["success"]:
        return _err(result["error"])
    return _ok()
