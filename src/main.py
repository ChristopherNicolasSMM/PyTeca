from __future__ import annotations

import os
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv
from flask import Flask, request, url_for
from flask.cli import with_appcontext
from flask_cors import CORS
from flask_login import LoginManager

from logs.setup_logging import configure_logging

# Carregar variáveis de ambiente
env_file = os.getenv("ENV_FILE")
if env_file:
    load_dotenv(env_file)
else:
    env_path = Path(".env")
    if not env_path.exists():
        env_path = Path("src") / ".env"
    load_dotenv(env_path)


def create_app():
    """Factory function para criar a aplicação Flask."""
    app = Flask(__name__, template_folder="templates", static_folder="static")

    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY", "dev-secret-key-change-in-production"
    )
    app.config["DEBUG"] = os.getenv("DEBUG", "True").lower() == "true"
    app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "uploads")
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 16777216))
    app.config["FLASK_ENV"] = os.getenv("FLASK_ENV", "DEV")

    configure_logging(app)

    from db.database import init_db
    from utils.dev_setup import ensure_dev_admin

    init_db(app)

    with app.app_context():
        ensure_dev_admin()

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Por favor, faça login para acessar esta página."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        from db.database import db
        from model.user import User

        return db.session.get(User, int(user_id))

    CORS(app)

    # Registrar blueprints básicos (autenticação, web, etc.)
    register_core_blueprints(app)

    # Registrar context processors (menu dinâmico via YAML)
    register_context_processors(app)

    # Registrar comandos CLI (apenas os essenciais)
    register_cli_commands(app)

    return app


def register_core_blueprints(app):
    """Registra os blueprints essenciais da aplicação."""
    try:
        from api.routes.auth_routes import auth_bp as api_auth_bp
        from api.routes.notifications_routes import notifications_bp
        from api.routes.register import register_bp
        from api.routes.book.book_routes import book_api_bp
        from api.routes.smart_list_routes import smart_list_api_bp   # ← NOVO

        from controller.auth import auth_bp
        from controller.web import web_bp
        from controller.book.book import book_bp

        app.register_blueprint(web_bp)
        app.register_blueprint(auth_bp,            url_prefix="/auth")
        app.register_blueprint(register_bp,        url_prefix="/api")
        app.register_blueprint(notifications_bp,   url_prefix="/api")
        app.register_blueprint(api_auth_bp)
        app.register_blueprint(book_bp)
        app.register_blueprint(book_api_bp)
        app.register_blueprint(smart_list_api_bp) 

        app.logger.info("Blueprints core registrados com sucesso.")
    except Exception as exc:
        app.logger.exception("Erro ao registrar blueprints core: %s", exc)
        raise

def register_context_processors(app):
    """Registra context processors, incluindo o menu dinâmico baseado em YAML."""

    @app.context_processor
    def inject_menu_from_yaml():
        """
        Carrega o menu do arquivo YAML correspondente à seção atual.
        A estrutura esperada nos arquivos YAML é:

        menu:
          - name: "Nome do Item"
            endpoint: "nome.do.endpoint"
            icon: "bi bi-house"  # opcional
            children: [...]       # opcional, para submenus
        """
        # Determina a seção atual a partir do primeiro segmento da URL
        path = request.path.strip("/")
        section = path.split("/")[0] if path else "home"
        
        
        print("DEBUG MAIN.PY")
        print(f"Carregando menu para seção: {section}")  # Debug
        print(f"URL atual: {request.url}")  # Debug
        print(f"Path atual: {path}")  # Debug
        print(10 * "\n")  # Debug
        
        
        

        # Caminhos possíveis para o arquivo YAML do menu
        section_yaml = os.path.join(app.template_folder, section, "menu.yaml")
        root_yaml = os.path.join(app.template_folder, "menu.yaml")

        yaml_file = None
        if os.path.exists(section_yaml):
            yaml_file = section_yaml
        elif os.path.exists(root_yaml):
            yaml_file = root_yaml

        menu_items = []
        if yaml_file:
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        menu_items = data.get("menu", [])
                    elif isinstance(data, list):
                        menu_items = data
            except Exception as e:
                app.logger.error("Erro ao carregar menu do YAML %s: %s", yaml_file, e)

        # Helper para construir URLs de forma segura nos templates
        def safe_url_for(endpoint, **values):
            if not endpoint:
                return "#"
            try:
                return url_for(endpoint, **values)
            except Exception:
                app.logger.debug(
                    "Endpoint '%s' não encontrado, retornando '#'", endpoint
                )
                return "#"

        return {"menu_items": menu_items, "safe_url_for": safe_url_for}


def register_cli_commands(app):
    """Registra comandos personalizados via Flask CLI."""

    @app.cli.command("init-admin")
    @click.option("--username", default="admin", show_default=True)
    @click.option("--email", default="admin@example.com", show_default=True)
    @click.option("--password", default="admin123", show_default=True)
    @with_appcontext
    def init_admin(username, email, password):
        from db.database import db
        from model.user import User

        admin = User.query.filter_by(username=username).first()
        if admin:
            click.echo(f"Usuário {username} já existe.")
            return

        admin = User(username=username, email=email, is_admin=True, is_active=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Usuário {username} criado com sucesso.")

    @app.cli.command("test-db")
    @with_appcontext
    def test_db():
        from db.database import test_connection

        if test_connection():
            click.echo("Conexão com o banco OK.")
        else:
            click.echo("Falha ao conectar com o banco.", err=True)

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "True").lower() == "true"

    https_enabled = os.getenv("HTTPS", "true" if debug else "false").lower() == "true"
    scheme = "https" if https_enabled else "http"
    
    app = create_app()

    app.logger.info(
        "Iniciando aplicação em %s://%s:%s (debug=%s)", scheme, host, port, debug
    )

    if https_enabled:
        app.run(host=host, port=port, debug=debug, ssl_context="adhoc")
    else:
        app.run(host=host, port=port, debug=debug)
