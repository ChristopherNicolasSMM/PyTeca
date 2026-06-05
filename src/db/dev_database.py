# src/db/database.py
from pathlib import Path
import pkgutil
import importlib
import model as model_pkg

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

db = SQLAlchemy()


def init_db(app):
    """Inicializa o banco de dados"""
    try:
        # Garantir que o diretório existe
        # Detectar se estamos em src/ ou na raiz
        current_dir = Path.cwd()
        if current_dir.name == "src":
            # Já estamos em src/, usar caminho relativo
            db_path = Path("instance")
        else:
            # Estamos na raiz, usar caminho com src/
            db_path = Path("src/instance")

        # Criar diretório e pais se necessário
        db_path.mkdir(parents=True, exist_ok=True)

        # Configurar SQLite com caminho absoluto normalizado
        db_path_abs = db_path.absolute().as_posix()
        database_uri = f"sqlite:///{db_path_abs}/pyteca_db.db"
        print(database_uri)
        app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        print(f"Database path: {database_uri}")

        # Inicializar db com app
        db.init_app(app)

        ## Importar modelos DEPOIS de inicializar o db
        with app.app_context():
 
            for importer, modname, ispkg in pkgutil.walk_packages(model_pkg.__path__, prefix="model."):
                if not ispkg:  # evita importar pacotes, apenas módulos
                    importlib.import_module(modname)   

            db.create_all()
            print("Tabelas core criadas com sucesso!")

    except Exception as e:
        print(f"Erro ao inicializar banco de dados: {e}")
        raise


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
