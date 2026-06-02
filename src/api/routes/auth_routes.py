"""
Auth API Routes
Endpoints para autenticação e preferências do usuário
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from db.database import db

logger = logging.getLogger(__name__)

auth_bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/update_theme", methods=["POST"])
@login_required
def update_theme():
    """
    Atualiza a preferência de tema do usuário (luz/escuro)

    Request JSON:
    {
        "modo_escuro": bool (true para escuro, false para claro)
    }

    Returns:
    {
        "success": bool,
        "message": str,
        "modo_escuro": bool
    }
    """
    try:
        data = request.get_json()

        if not data or "modo_escuro" not in data:
            return (
                jsonify({"success": False, "message": "modo_escuro é obrigatório"}),
                400,
            )

        # Atualizar preferência de tema do usuário
        modo_escuro = data.get("modo_escuro")

        if not isinstance(modo_escuro, bool):
            return (
                jsonify(
                    {"success": False, "message": "modo_escuro deve ser um booleano"}
                ),
                400,
            )

        current_user.modo_escuro = modo_escuro
        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": f'Tema alterado para {"escuro" if modo_escuro else "claro"}',
                    "modo_escuro": modo_escuro,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        logger.exception("Erro ao atualizar tema: %s", e)
        return jsonify({"success": False, "message": "Erro ao atualizar tema"}), 500
