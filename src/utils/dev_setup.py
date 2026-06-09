"""
Utilitário para configuração automática do ambiente de desenvolvimento.
"""

import os

from db.database import db
from model.core.user import User

      
def ensure_dev_admin():
    """
    Garante que existe um usuário admin no ambiente de desenvolvimento.
    Cria automaticamente se não existir com senha '123'.
    """
    # Verificar se é ambiente de desenvolvimento
    flask_env = os.getenv("FLASK_ENV", "DEV")
    debug = os.getenv("DEBUG", "True").lower() == "true"

    if flask_env != "DEV" and not debug:
        # Não é ambiente de desenvolvimento, não fazer nada
        return False

    try:
        # Verificar se já existe admin
        admin = User.query.filter_by(username="admin").first()

        if not admin:
            # Criar admin
            admin = User(
                username="admin",
                email="admin@brewstation.com",
                is_admin=True,
                is_active=True,
            )
            admin.set_password("123")

            db.session.add(admin)
            db.session.commit()

            print(
                "✅ Usuário admin criado automaticamente (usuário: admin, senha: 123)"
            )
            ensure_default_roles_and_permissions()
            return True
        else:
            # Admin já existe, garantir que está ativo
            if not admin.is_active:
                admin.is_active = True
                db.session.commit()
                print("✅ Usuário admin reativado")

            # Resetar senha para '123' em desenvolvimento
            admin.set_password("123")
            db.session.commit()
            print("✅ Senha do admin resetada para '123' (desenvolvimento)")
            ensure_default_roles_and_permissions()
            return False
    except Exception as e:
        print(f"⚠️  Erro ao verificar/criar admin: {e}")
        db.session.rollback()
        return False

def ensure_default_roles_and_permissions():
    """Cria papel 'admin' com permissão 'admin' e associa ao usuário admin."""
    from model.core.role import Role
    from model.core.permission import Permission
    from model.core.user import User
    from db.database import db

    # Criar permissão admin
    admin_perm = Permission.query.filter_by(name="admin").first()
    if not admin_perm:
        admin_perm = Permission(name="admin", description="Acesso total ao sistema")
        db.session.add(admin_perm)

    # Criar papel admin
    admin_role = Role.query.filter_by(name="admin").first()
    if not admin_role:
        admin_role = Role(name="admin", description="Administrador")
        db.session.add(admin_role)
        db.session.commit()
        admin_role.permissions.append(admin_perm)
        db.session.commit()

    # Atribuir papel admin ao usuário admin (se existir)
    admin_user = User.query.filter_by(username="admin").first()
    if admin_user and admin_role not in admin_user.roles:
        admin_user.roles.append(admin_role)
        db.session.commit()
