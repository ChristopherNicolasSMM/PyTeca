# routes/notifications_routes.py
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from db.database import db
from model.notification import Notification, NotificationTrash

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/notifications", methods=["GET"])
@login_required
def get_notifications():
    """Obter notificações do usuário"""
    try:
        # Parâmetros de paginação
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        unread_only = request.args.get("unread_only", "false").lower() == "true"

        # Query base
        query = Notification.query.filter_by(user_id=current_user.id)

        # Filtrar apenas não lidas se solicitado
        if unread_only:
            query = query.filter_by(is_read=False)

        # Ordenar e paginar
        notifications = query.order_by(
            Notification.priority.desc(), Notification.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        # Calcular estatísticas adicionais
        total_notifications = Notification.query.filter_by(
            user_id=current_user.id
        ).count()
        unread_count = Notification.query.filter_by(
            user_id=current_user.id, is_read=False
        ).count()

        # Contar urgentes (priority >= 2)
        urgent_count = (
            Notification.query.filter_by(user_id=current_user.id)
            .filter(Notification.priority >= 2)
            .count()
        )

        # Estimar semana (simplificado - pode ser melhorado)
        week_ago = datetime.now() - timedelta(days=7)
        week_count = (
            Notification.query.filter_by(user_id=current_user.id)
            .filter(Notification.created_at >= week_ago)
            .count()
        )

        return (
            jsonify(
                {
                    "notifications": [
                        notification.to_dict() for notification in notifications.items
                    ],
                    "total": notifications.total,
                    "pages": notifications.pages,
                    "current_page": page,
                    "unread_count": unread_count,
                    "week_count": week_count,
                    "urgent_count": urgent_count,
                }
            ),
            200,
        )

    except Exception as e:
        print(f"Erro ao buscar notificações: {e}")
        return jsonify({"error": "Erro interno do servidor"}), 500


@notifications_bp.route("/notifications/<int:notification_id>/read", methods=["PUT"])
@login_required
def mark_notification_read(notification_id):
    """Marcar notificação como lida"""
    try:
        notification = Notification.query.filter_by(
            id=notification_id, user_id=current_user.id
        ).first()

        if not notification:
            return jsonify({"error": "Notificação não encontrada"}), 404

        notification.is_read = True
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Notificação marcada como lida",
                    "notification": notification.to_dict(),
                }
            ),
            200,
        )

    except Exception as e:
        print(f"Erro ao marcar notificação como lida: {e}")
        db.session.rollback()
        return jsonify({"error": "Erro interno do servidor"}), 500


@notifications_bp.route("/notifications/read-all", methods=["PUT"])
@login_required
def mark_all_notifications_read():
    """Marcar todas as notificações como lidas"""
    try:
        updated = Notification.query.filter_by(
            user_id=current_user.id, is_read=False
        ).update({"is_read": True})

        db.session.commit()

        return (
            jsonify(
                {
                    "message": f"{updated} notificações marcadas como lidas",
                    "updated_count": updated,
                }
            ),
            200,
        )

    except Exception as e:
        print(f"Erro ao marcar todas as notificações como lidas: {e}")
        db.session.rollback()
        return jsonify({"error": "Erro interno do servidor"}), 500


@notifications_bp.route("/notifications/<int:notification_id>", methods=["DELETE"])
@login_required
def delete_notification(notification_id):
    """Excluir notificação (mover para lixeira)"""
    try:
        notification = Notification.query.filter_by(
            id=notification_id, user_id=current_user.id
        ).first()

        if not notification:
            return jsonify({"error": "Notificação não encontrada"}), 404

        # Mover para lixeira
        trash_notification = NotificationTrash(
            original_notification_id=notification.id,
            user_id=notification.user_id,
            title=notification.title,
            message=notification.message,
            notification_type=notification.notification_type,
            is_read=notification.is_read,
            action_url=notification.action_url,
            action_params=notification.action_params,
            icon=notification.icon,
            priority=notification.priority,
            created_at=notification.created_at,
        )

        db.session.add(trash_notification)
        db.session.delete(notification)
        db.session.commit()

        return jsonify({"message": "Notificação excluída com sucesso"}), 200

    except Exception as e:
        print(f"Erro ao excluir notificação: {e}")
        db.session.rollback()
        return jsonify({"error": "Erro interno do servidor"}), 500


@notifications_bp.route("/notifications/create", methods=["POST"])
@login_required
def create_notification():
    """Criar nova notificação (útil para testes)"""
    try:
        data = request.get_json()

        notification = Notification(
            user_id=current_user.id,
            title=data.get("title"),
            message=data["message"],
            notification_type=data.get("notification_type", "info"),
            action_url=data.get("action_url"),
            action_params=data.get("action_params"),
            icon=data.get("icon", "bi-bell"),
            priority=data.get("priority", 0),
        )

        db.session.add(notification)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Notificação criada com sucesso",
                    "notification": notification.to_dict(),
                }
            ),
            201,
        )

    except Exception as e:
        print(f"Erro ao criar notificação: {e}")
        db.session.rollback()
        return jsonify({"error": "Erro interno do servidor"}), 500


@notifications_bp.route("/notifications/clear-all", methods=["DELETE"])
@login_required
def clear_all_notifications():
    """Limpar todas as notificações do usuário"""
    try:
        # Contar quantas notificações serão excluídas
        count = Notification.query.filter_by(user_id=current_user.id).count()

        # Mover todas para lixeira
        notifications = Notification.query.filter_by(user_id=current_user.id).all()

        for notification in notifications:
            trash_notification = NotificationTrash(
                original_notification_id=notification.id,
                user_id=notification.user_id,
                title=notification.title,
                message=notification.message,
                notification_type=notification.notification_type,
                is_read=notification.is_read,
                action_url=notification.action_url,
                action_params=notification.action_params,
                icon=notification.icon,
                priority=notification.priority,
                created_at=notification.created_at,
            )
            db.session.add(trash_notification)
            db.session.delete(notification)

        db.session.commit()

        return (
            jsonify(
                {
                    "message": f"{count} notificações limpas com sucesso",
                    "cleared_count": count,
                }
            ),
            200,
        )

    except Exception as e:
        print(f"Erro ao limpar notificações: {e}")
        db.session.rollback()
        return jsonify({"error": "Erro interno do servidor"}), 500


@notifications_bp.route("/notifications/stats", methods=["GET"])
@login_required
def get_notification_stats():
    """Obter estatísticas das notificações"""
    try:
        total = Notification.query.filter_by(user_id=current_user.id).count()
        unread = Notification.query.filter_by(
            user_id=current_user.id, is_read=False
        ).count()
        read = total - unread

        # Contar por tipo
        types = (
            db.session.query(
                Notification.notification_type, db.func.count(Notification.id)
            )
            .filter_by(user_id=current_user.id)
            .group_by(Notification.notification_type)
            .all()
        )

        type_stats = {tipo: count for tipo, count in types}

        return (
            jsonify(
                {"total": total, "unread": unread, "read": read, "by_type": type_stats}
            ),
            200,
        )

    except Exception as e:
        print(f"Erro ao buscar estatísticas de notificações: {e}")
        return jsonify({"error": "Erro interno do servidor"}), 500


@notifications_bp.route("/notifications/teste", methods=["GET"])
@login_required
def testeNotificacoes():
    try:
        notification = Notification(
            user_id=1,
            title="Novo Dispositivo Conectado",
            message="iSpindel-01 conectou-se ao sistema",
            notification_type="success",
            action_url="/dispositivos",
            action_params={"device_id": 123},
            icon="bi-wifi",
            priority=1,
        )

        db.session.add(notification)
        db.session.commit()
        return (
            jsonify(
                {
                    "message": "Notificação criada com sucesso",
                    "notification": notification.to_dict(),
                }
            ),
            202,
        )

    except Exception as e:
        print(f"Erro ao buscar estatísticas de notificações: {e}")
        return jsonify({"error": "Erro interno do servidor"}), 500
