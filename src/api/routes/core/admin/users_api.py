from __future__ import annotations

import re

from flask import Blueprint, jsonify, request
from flask_login import login_required

from utils.permissions import permission_required
from model.core.user import User
from db.database import db

users_api_bp = Blueprint("users_api", __name__, url_prefix="/api/admin/users")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _ok(data=None, code=200):
    return jsonify({"success": True, **(data or {})}), code


def _err(message, code=400, **extra):
    return jsonify({"success": False, "error": message, **extra}), code


def _user_to_dict(u: User) -> dict:
    d = u.to_dict()
    d.pop("password_hash", None)  # to_dict() já não inclui, mas garante por segurança
    return d


# ── Validação dos campos obrigatórios de cadastro ───────────────────────────

def _validate_payload(data: dict, *, is_update: bool = False, current_user_id: int | None = None) -> list[str]:
    errors = []

    def _required(field, label):
        if not (data.get(field) or "").strip():
            errors.append(f"{label} é obrigatório.")

    _required("username", "Usuário (login)")
    _required("email", "E-mail")
    _required("nome", "Nickname")
    _required("nome_completo", "Nome completo")
    _required("celular", "Celular")

    if not is_update:
        _required("password", "Senha")

    email = (data.get("email") or "").strip()
    if email and not _EMAIL_RE.match(email):
        errors.append("E-mail em formato inválido.")

    username = (data.get("username") or "").strip()
    if username:
        existing = User.query.filter_by(username=username).first()
        if existing and existing.id != current_user_id:
            errors.append(f"Já existe um usuário com o login '{username}'.")

    if email:
        existing = User.query.filter_by(email=email).first()
        if existing and existing.id != current_user_id:
            errors.append(f"Já existe um usuário com o e-mail '{email}'.")

    cpf = (data.get("cpf") or "").strip()
    if cpf:
        from utils.validators import validate_cpf
        if not validate_cpf(cpf):
            errors.append("CPF inválido (dígito verificador não confere).")
        else:
            from utils.validators import format_cpf, only_digits
            existing = User.query.filter_by(cpf=format_cpf(cpf)).first()
            if existing and existing.id != current_user_id:
                errors.append("Este CPF já está cadastrado para outro usuário.")

    uf = (data.get("endereco_uf") or "").strip()
    if uf and len(uf) != 2:
        errors.append("UF deve ter 2 letras (ex: SP, RJ).")

    return errors


def _apply_payload(user: User, data: dict, *, is_update: bool = False) -> None:
    user.username = data["username"].strip()
    user.email = data["email"].strip()
    user.nome = data["nome"].strip()
    user.nome_completo = data["nome_completo"].strip()
    user.celular = data["celular"].strip()

    if data.get("password"):
        user.set_password(data["password"])

    if "cpf" in data:
        user.set_cpf(data.get("cpf") or None)

    for field in ("endereco_rua", "endereco_numero", "endereco_complemento",
                   "endereco_bairro", "endereco_cidade", "endereco_uf", "endereco_cep",
                   "empresa", "cargo", "pais", "telefone"):
        if field in data:
            setattr(user, field, (data.get(field) or "").strip() or None)

    if "is_admin" in data:
        user.is_admin = bool(data["is_admin"])
    if "is_active" in data:
        user.is_active = bool(data["is_active"])


# ── Endpoints ────────────────────────────────────────────────────────────────

@users_api_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def list_users():
    users = User.query.order_by(User.username).all()
    return _ok({"users": [_user_to_dict(u) for u in users]})


@users_api_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("admin")
def get_user(id: int):
    user = User.query.get(id)
    if not user:
        return _err("Usuário não encontrado.", 404)
    return _ok({"user": _user_to_dict(user)})


@users_api_bp.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create_user():
    data = request.get_json(silent=True) or {}
    errors = _validate_payload(data, is_update=False)
    if errors:
        return _err("Dados inválidos.", 422, errors=errors)

    user = User(is_active=True, is_admin=bool(data.get("is_admin", False)))
    try:
        _apply_payload(user, data, is_update=False)
    except ValueError as e:
        return _err(str(e), 422)

    db.session.add(user)
    db.session.commit()
    return _ok({"user": _user_to_dict(user)}, 201)


@users_api_bp.route("/<int:id>", methods=["PUT"])
@login_required
@permission_required("admin")
def update_user(id: int):
    user = User.query.get(id)
    if not user:
        return _err("Usuário não encontrado.", 404)

    data = request.get_json(silent=True) or {}
    errors = _validate_payload(data, is_update=True, current_user_id=user.id)
    if errors:
        return _err("Dados inválidos.", 422, errors=errors)

    try:
        _apply_payload(user, data, is_update=True)
    except ValueError as e:
        return _err(str(e), 422)

    db.session.commit()
    return _ok({"user": _user_to_dict(user)})


@users_api_bp.route("/<int:id>/deactivate", methods=["POST"])
@login_required
@permission_required("admin")
def deactivate_user(id: int):
    user = User.query.get(id)
    if not user:
        return _err("Usuário não encontrado.", 404)
    user.is_active = False
    db.session.commit()
    return _ok({"message": f"Usuário '{user.username}' desativado."})


@users_api_bp.route("/<int:id>/activate", methods=["POST"])
@login_required
@permission_required("admin")
def activate_user(id: int):
    user = User.query.get(id)
    if not user:
        return _err("Usuário não encontrado.", 404)
    user.is_active = True
    db.session.commit()
    return _ok({"message": f"Usuário '{user.username}' ativado."})
