"""
Blueprint centralizado para endpoints de API da interface web.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from db.database import db
from services.notifications_service import (
    create_notification,
    delete_trash_entry,
    list_notifications,
    list_trash,
    mark_as_read,
    mark_as_unread,
    move_to_trash,
    restore_from_trash,
)
from services.profile_service import (
    change_password,
    update_notification_preferences_from_form,
    update_notification_preferences_from_json,
    update_profile_from_form,
    update_profile_from_json,
)

api_bp = Blueprint("api", __name__)

logger = logging.getLogger(__name__)


def _json_or_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


@api_bp.route("/atualizar_perfil", methods=["POST"])
@api_bp.route("/v1/users/profile", methods=["POST"])
@login_required
def atualizar_perfil():
    try:
        if request.form:
            update_profile_from_form(current_user, request.form, request.files)
            return jsonify({"message": "Perfil atualizado com sucesso"}), 200

        payload = request.get_json(silent=True)
        if not payload:
            return _json_or_error("Nenhum dado enviado")

        update_profile_from_json(current_user, payload)
        return (
            jsonify(
                {
                    "message": "Perfil atualizado com sucesso",
                    "user": {
                        "nome_completo": current_user.nome_completo,
                        "email": current_user.email,
                        "empresa": current_user.empresa,
                        "cargo": current_user.cargo,
                    },
                }
            ),
            200,
        )
    except ValueError as err:
        db.session.rollback()
        return _json_or_error(str(err))
    except Exception as exc:  # pragma: no cover - salvaguarda
        db.session.rollback()
        logger.exception("Erro ao atualizar perfil: {exc}", exc_info=exc)
        return _json_or_error("Erro ao atualizar perfil"), 500


@api_bp.route("/atualizar_configuracoes", methods=["POST"])
@api_bp.route("/v1/users/preferences", methods=["POST"])
@login_required
def atualizar_configuracoes():
    try:
        if request.form:
            update_notification_preferences_from_form(current_user, request.form)
            return jsonify({"message": "Configurações atualizadas com sucesso"}), 200

        payload = request.get_json(silent=True)
        if not payload:
            return _json_or_error("Nenhum dado enviado")

        update_notification_preferences_from_json(current_user, payload)
        return (
            jsonify(
                {
                    "message": "Configurações atualizadas com sucesso",
                    "configuracoes": {
                        "notificacao_alteracoes": current_user.notificacao_alteracoes,
                        "notificacao_novos_produtos": current_user.notificacao_novos_produtos,
                        "notificacao_ofertas": current_user.notificacao_ofertas,
                    },
                }
            ),
            200,
        )
    except Exception as exc:  # pragma: no cover
        db.session.rollback()
        logger.exception("Erro ao atualizar configurações: %s", exc)
        return _json_or_error("Erro ao atualizar configurações"), 500


@api_bp.route("/alterar_senha", methods=["POST"])
@api_bp.route("/v1/users/change-password", methods=["POST"])
@login_required
def alterar_senha():
    data = request.form or (request.get_json(silent=True) or {})
    senha_atual = data.get("currentPassword") or data.get("senha_atual")
    nova_senha = data.get("newPassword") or data.get("nova_senha")
    confirmar_senha = data.get("renewPassword") or data.get("confirmar_senha")

    if not all([senha_atual, nova_senha, confirmar_senha]):
        return _json_or_error("Todos os campos são obrigatórios")

    try:
        change_password(current_user, senha_atual, nova_senha, confirmar_senha)
        return jsonify({"message": "Senha alterada com sucesso"}), 200
    except ValueError as err:
        db.session.rollback()
        return _json_or_error(str(err))
    except Exception as exc:  # pragma: no cover
        db.session.rollback()
        logger.exception("Erro ao alterar senha: %s", exc)
        return _json_or_error("Erro ao alterar senha"), 500


@api_bp.route("/notifications", methods=["GET", "POST"])
@api_bp.route("/v1/notifications", methods=["GET", "POST"])
@login_required
def notifications():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        if not payload.get("message"):
            return _json_or_error("Mensagem é obrigatória")
        notification = create_notification(
            current_user.id, payload["message"], payload.get("title")
        )
        return (
            jsonify(
                {
                    "message": "Notificação criada",
                    "notification": notification.to_dict(),
                }
            ),
            201,
        )

    status = request.args.get("status")
    notifications = list_notifications(current_user.id, status=status)
    return (
        jsonify(
            {
                "notifications": [
                    notification.to_dict() for notification in notifications
                ]
            }
        ),
        200,
    )


@api_bp.route("/notifications/<int:notif_id>/read", methods=["POST"])
@api_bp.route("/v1/notifications/<int:notif_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notif_id: int):
    try:
        notification = mark_as_read(current_user.id, notif_id)
        return (
            jsonify(
                {
                    "message": "Notificação marcada como lida",
                    "notification": notification.to_dict(),
                }
            ),
            200,
        )
    except ValueError as err:
        return _json_or_error(str(err), 404)


@api_bp.route("/notifications/<int:notif_id>/unread", methods=["POST"])
@api_bp.route("/v1/notifications/<int:notif_id>/unread", methods=["POST"])
@login_required
def mark_notification_unread(notif_id: int):
    try:
        notification = mark_as_unread(current_user.id, notif_id)
        return (
            jsonify(
                {
                    "message": "Notificação marcada como não lida",
                    "notification": notification.to_dict(),
                }
            ),
            200,
        )
    except ValueError as err:
        return _json_or_error(str(err), 404)


@api_bp.route("/notifications/<int:notif_id>/trash", methods=["POST"])
@api_bp.route("/v1/notifications/<int:notif_id>/trash", methods=["POST"])
@login_required
def move_notification_to_trash(notif_id: int):
    try:
        trashed = move_to_trash(current_user.id, notif_id)
        return (
            jsonify(
                {
                    "message": "Notificação movida para a lixeira",
                    "trash": trashed.to_dict(),
                }
            ),
            200,
        )
    except ValueError as err:
        return _json_or_error(str(err), 404)


@api_bp.route("/notifications/trash", methods=["GET"])
@api_bp.route("/v1/notifications/trash", methods=["GET"])
@login_required
def list_trash_notifications():
    trash = list_trash(current_user.id)
    return jsonify({"trash": [item.to_dict() for item in trash]}), 200


@api_bp.route("/notifications/trash/<int:trash_id>/restore", methods=["POST"])
@api_bp.route("/v1/notifications/trash/<int:trash_id>/restore", methods=["POST"])
@login_required
def restore_trash_notification(trash_id: int):
    try:
        notification = restore_from_trash(current_user.id, trash_id)
        return (
            jsonify(
                {
                    "message": "Notificação restaurada",
                    "notification": notification.to_dict(),
                }
            ),
            200,
        )
    except ValueError as err:
        return _json_or_error(str(err), 404)


@api_bp.route("/notifications/trash/<int:trash_id>", methods=["DELETE"])
@api_bp.route("/v1/notifications/trash/<int:trash_id>", methods=["DELETE"])
@login_required
def delete_trash_notification(trash_id: int):
    try:
        delete_trash_entry(current_user.id, trash_id)
        return jsonify({"message": "Excluída definitivamente"}), 200
    except ValueError as err:
        return _json_or_error(str(err), 404)


@api_bp.route("/notifications/count", methods=["GET"])
@api_bp.route("/v1/notifications/count", methods=["GET"])
@login_required
def unread_notifications_count():
    count = len(list_notifications(current_user.id, status="unread"))
    return jsonify({"unread": count}), 200


@api_bp.route("/auth/update_theme", methods=["POST"])
@login_required
def update_theme():
    """Atualiza a preferência de tema do usuário"""
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return _json_or_error("Nenhum dado enviado")

        modo_escuro = payload.get("modo_escuro", False)
        current_user.modo_escuro = bool(modo_escuro)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Tema atualizado com sucesso",
                    "modo_escuro": current_user.modo_escuro,
                }
            ),
            200,
        )
    except Exception as exc:
        db.session.rollback()
        logger.exception("Erro ao atualizar tema: %s", exc)
        return _json_or_error("Erro ao atualizar tema"), 500
