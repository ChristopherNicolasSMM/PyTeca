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

            return False
    except Exception as e:
        print(f"⚠️  Erro ao verificar/criar admin: {e}")
        db.session.rollback()
        return False
