from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required

from utils.permissions import permission_required
from model.core.role import Role
from model.core.permission import Permission
from model.core.user import User
from db.database import db

roles_api_bp = Blueprint("roles_api", __name__, url_prefix="/api/admin/roles")


def _ok(data=None, code=200):
    return jsonify({"success": True, **(data or {})}), code


def _err(message, code=400):
    return jsonify({"success": False, "error": message}), code


def _role_to_dict(r: Role) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "permissions": [{"id": p.id, "name": p.name, "description": p.description} for p in r.permissions],
        "user_count": len(r.users),
    }


def _permission_to_dict(p: Permission) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        # Agrupador visual: "books.trash" -> grupo "books" — ajuda a UI a
        # organizar a lista de permissões sem precisar de uma coluna extra.
        "group": p.name.split(".")[0] if "." in p.name else "geral",
    }


# ── Roles ──────────────────────────────────────────────────────────────────

@roles_api_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def list_roles():
    roles = Role.query.order_by(Role.name).all()
    return _ok({"roles": [_role_to_dict(r) for r in roles]})


@roles_api_bp.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create_role():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return _err("Nome do papel é obrigatório.")
    if Role.query.filter_by(name=name).first():
        return _err(f"Já existe um papel chamado '{name}'.", 409)

    role = Role(name=name, description=data.get("description", "").strip() or None)
    db.session.add(role)
    db.session.commit()
    return _ok({"role": _role_to_dict(role)}, 201)


@roles_api_bp.route("/<int:id>", methods=["DELETE"])
@login_required
@permission_required("admin")
def delete_role(id: int):
    role = Role.query.get(id)
    if not role:
        return _err("Papel não encontrado.", 404)
    if role.name == "admin":
        return _err("O papel 'admin' não pode ser removido — é a rede de segurança do sistema.", 403)
    db.session.delete(role)
    db.session.commit()
    return _ok({"message": "Papel removido."})


# ── Associação Role <-> Permission (a UI NUNCA cria Permission aqui) ────────

@roles_api_bp.route("/<int:role_id>/permissions/<int:perm_id>", methods=["POST"])
@login_required
@permission_required("admin")
def attach_permission(role_id: int, perm_id: int):
    role = Role.query.get(role_id)
    perm = Permission.query.get(perm_id)
    if not role or not perm:
        return _err("Papel ou permissão não encontrados.", 404)
    if perm not in role.permissions:
        role.permissions.append(perm)
        db.session.commit()
    return _ok({"role": _role_to_dict(role)})


@roles_api_bp.route("/<int:role_id>/permissions/<int:perm_id>", methods=["DELETE"])
@login_required
@permission_required("admin")
def detach_permission(role_id: int, perm_id: int):
    role = Role.query.get(role_id)
    perm = Permission.query.get(perm_id)
    if not role or not perm:
        return _err("Papel ou permissão não encontrados.", 404)
    if perm in role.permissions:
        role.permissions.remove(perm)
        db.session.commit()
    return _ok({"role": _role_to_dict(role)})


# ── Permissões disponíveis (somente leitura — geradas pelo código) ─────────

@roles_api_bp.route("/permissions", methods=["GET"])
@login_required
@permission_required("admin")
def list_permissions():
    """
    Lista TODAS as permissões já sincronizadas a partir do código
    (rotas geradas + @permission nos models). Esta API não tem
    endpoint de criação — permissões nascem exclusivamente da
    sincronização automática em utils/permissions_sync.py.
    """
    perms = Permission.query.order_by(Permission.name).all()
    return _ok({"permissions": [_permission_to_dict(p) for p in perms]})


# ── Atribuição de Role a usuários ───────────────────────────────────────────

@roles_api_bp.route("/users", methods=["GET"])
@login_required
@permission_required("admin")
def list_users_with_roles():
    users = User.query.order_by(User.username).all()
    return _ok({
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "nome": u.nome,
                "nome_completo": u.nome_completo,
                "celular": u.celular,
                "cpf": u.cpf,
                "is_admin": u.is_admin,
                "is_active": u.is_active,
                "roles": [{"id": r.id, "name": r.name} for r in u.roles],
            }
            for u in users
        ]
    })


@roles_api_bp.route("/users/<int:user_id>/roles/<int:role_id>", methods=["POST"])
@login_required
@permission_required("admin")
def assign_role(user_id: int, role_id: int):
    user = User.query.get(user_id)
    role = Role.query.get(role_id)
    if not user or not role:
        return _err("Usuário ou papel não encontrados.", 404)
    if role not in user.roles:
        user.roles.append(role)
        db.session.commit()
    return _ok({"message": f"Papel '{role.name}' atribuído a {user.username}."})


@roles_api_bp.route("/users/<int:user_id>/roles/<int:role_id>", methods=["DELETE"])
@login_required
@permission_required("admin")
def revoke_role(user_id: int, role_id: int):
    user = User.query.get(user_id)
    role = Role.query.get(role_id)
    if not user or not role:
        return _err("Usuário ou papel não encontrados.", 404)
    if role in user.roles:
        user.roles.remove(role)
        db.session.commit()
    return _ok({"message": f"Papel '{role.name}' revogado de {user.username}."})
