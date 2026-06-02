# src/db/database.py
import os
from pathlib import Path
from urllib.parse import quote_plus

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

db = SQLAlchemy()


def init_db(app):
    """Inicializa o banco de dados"""
    try:
        # Configuração do PostgreSQL com Neon
        database_uri = get_neon_connection_string()
        app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }

        print(f"Database URI: {database_uri.split('@')[0]}@***")  # Log seguro

        # Inicializar db com app
        db.init_app(app)

        # Importar modelos DEPOIS de inicializar o db
        with app.app_context():
            # Importar todos os modelos para garantir registro
            pass
            # Adicione outros modelos conforme necessário

            # Criar tabelas
            db.create_all()
            print("✅ Tabelas criadas com sucesso no PostgreSQL/Neon!")

    except Exception as e:
        print(f"❌ Erro ao inicializar banco de dados: {e}")
        raise


def get_neon_connection_string():
    """Obtém a string de conexão do Neon PostgreSQL"""

    # Opção 1: Via variáveis de ambiente (RECOMENDADO)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Se já estiver no formato correto
        if database_url.startswith("postgresql://"):
            return database_url
        # Converter de postgres:// para postgresql://
        elif database_url.startswith("postgres://"):
            return database_url.replace("postgres://", "postgresql://", 1)

    # Opção 2: Via variáveis de ambiente individuais
    user = os.getenv("NEON_USER")
    password = os.getenv("NEON_PASSWORD")
    host = os.getenv("NEON_HOST")
    port = os.getenv("NEON_PORT", "5432")
    database = os.getenv("NEON_DATABASE")

    if all([user, password, host, database]):
        # Codificar a senha para URL
        encoded_password = quote_plus(password)
        return f"postgresql://{user}:{encoded_password}@{host}:{port}/{database}"

    # Opção 3: Fallback para SQLite (desenvolvimento)
    print(
        "⚠️  Variáveis de ambiente do Neon não encontradas. Usando SQLite como fallback."
    )

    # Garantir que o diretório existe
    db_path = Path("instance")
    db_path.mkdir(exist_ok=True)

    return f"sqlite:///{db_path.absolute()}/brewstation.db"


def get_db():
    """Retorna a instância do banco de dados"""
    return db


def test_connection():
    """Testa a conexão com o banco de dados"""
    from flask import current_app

    try:
        with current_app.app_context():
            # A correção é aqui: usa text() para encapsular a string SQL
            db.session.execute(text("SELECT 1"))
            # A chamada db.session.commit() é necessária se uma transação for aberta,
            # mas SELECT 1 geralmente não a abre e é apenas para verificação de conexão.
            # No entanto, em alguns casos, chamar commit ou fechar a sessão pode ser mais seguro.
            db.session.commit()

            print("✅ Conexão com o banco de dados estabelecida com sucesso!")
            return True
    except Exception as e:
        # Revertendo a sessão em caso de erro para liberar recursos.
        db.session.rollback()
        print(f"❌ Erro na conexão com o banco: {e}")
        return False
