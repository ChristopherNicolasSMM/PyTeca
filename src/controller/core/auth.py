"""
Controlador de autenticação
"""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user

from db.database import db
from model.core.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    """Endpoint para login do usuário"""
    data = request.get_json()

    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username e password são obrigatórios"}), 400

    user = User.query.filter_by(username=data["username"]).first()
    if user and user.check_password(data["password"]):
        if user.is_active:
            login_user(user)
            return (
                jsonify(
                    {"message": "Login realizado com sucesso", "user": user.to_dict()}
                ),
                200,
            )
        else:
            return jsonify({"error": "Usuário inativo"}), 401
    else:
        return jsonify({"error": "Credenciais inválidas"}), 401


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """Endpoint para logout do usuário"""
    logout_user()
    return jsonify({"message": "Logout realizado com sucesso"}), 200


@auth_bp.route("/register", methods=["POST"])
def register():
    """Endpoint para registro de novo usuário"""
    data = request.get_json()

    if (
        not data
        or not data.get("username")
        or not data.get("email")
        or not data.get("password")
    ):
        return jsonify({"error": "Username, email e password são obrigatórios"}), 400

    # Verificar se usuário já existe
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Username já existe"}), 400

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email já existe"}), 400

    # Criar novo usuário
    user = User(username=data["username"], email=data["email"])
    user.set_password(data["password"])

    db.session.add(user)
    db.session.commit()

    return (
        jsonify({"message": "Usuário criado com sucesso", "user": user.to_dict()}),
        201,
    )


@auth_bp.route("/profile", methods=["GET"])
@login_required
def profile():
    """Endpoint para obter perfil do usuário logado"""
    return jsonify({"user": current_user.to_dict()}), 200


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    """Endpoint para alterar senha do usuário"""
    data = request.get_json()

    if not data or not data.get("current_password") or not data.get("new_password"):
        return jsonify({"error": "Senha atual e nova senha são obrigatórias"}), 400

    if not current_user.check_password(data["current_password"]):
        return jsonify({"error": "Senha atual incorreta"}), 401

    current_user.set_password(data["new_password"])
    db.session.commit()

    return jsonify({"message": "Senha alterada com sucesso"}), 200
