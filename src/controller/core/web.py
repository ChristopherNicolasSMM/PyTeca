"""
Rotas voltadas para páginas HTML.
"""

from __future__ import annotations

import logging
from pathlib import Path

from utils.generate_model.menu_builder import menu_item
from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

logger = logging.getLogger(__name__)
 
web_bp = Blueprint("web", __name__)

TEMPLATE_ROOT = Path("src") / "templates"


def render_app_template(template_name: str, **context):
    """
    Helper centralizado que garante que o template existe antes de renderizar.
    Tenta primeiro nos templates do core, depois nos templates dos plugins ativos.
    """
    # O template loader customizado já cuida de buscar nos plugins
    # Então podemos usar render_template diretamente
    try:
        return render_template(template_name, **context)
    except Exception as e:
        logger.warning(
            "Template %s não encontrado: %s. Retornando 404.", template_name, e
        )
        abort(404)


@web_bp.route("/556")
@login_required
@menu_item("556", icon="bi-speedometer2")#, parent="Relatórios")
def index_556():
    return render_app_template("core/556.html")


@web_bp.route("/")
def index():
    if current_user.is_authenticated:
        return render_app_template("core/bem_vindo.html")
    return redirect(url_for("web.login"))


@web_bp.route("/reset_password")
def reset_password():
    print("Resetando banco de dados...")
    from db.database import db

    db.create_all()
    print("Banco de dados resetado!")
    print("Criando usuário admin...")

    from model.core.user import User

    admin = User.query.filter_by(username="admin").first()
    if admin:
        print(f"Usuário admin Existe.")

        admin.set_password("admin123")
        db.session.add(admin)

        print("Senha do usuário admin criada com sucesso!")
        print("Redirecionando para a página de login...")
        print(url_for("web.login"))
        print("Redirecionando...")

    return redirect(url_for("web.login"))


@web_bp.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))
    return render_app_template("core/login.html")


@web_bp.route("/register")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))
    return render_app_template("core/register.html")


@web_bp.route("/dashboard")
@login_required
def dashboard():
    return render_app_template("core/dashboard.html")


@web_bp.route("/config")
@login_required
def config():
    return render_app_template("core/config.html")



@web_bp.route("/profile")
@login_required
def profile():
    return render_app_template("core/profile.html")


# @web_bp.route("/perfil")
# @login_required
# def perfil():
#    return render_app_template("core/perfil.html")


@web_bp.route("/atualizar_perfil", methods=["POST"])
@login_required
def atualizar_perfil():
    """Rota web para atualizar perfil"""
    from flask import redirect, request, url_for

    from db.database import db
    from services.core.profile_service import update_profile_from_form

    try:
        update_profile_from_form(current_user, request.form, request.files)
        flash("Perfil atualizado com sucesso!", "success")
        return redirect(url_for("web.profile"))
    except ValueError as err:
        db.session.rollback()
        flash(str(err), "error")
        return redirect(url_for("web.profile"))
    except Exception as exc:
        db.session.rollback()
        logger.exception("Erro ao atualizar perfil: %s", exc)
        flash("Erro ao atualizar perfil", "error")
        return redirect(url_for("web.profile"))


@web_bp.route("/atualizar_configuracoes", methods=["POST"])
@login_required
def atualizar_configuracoes():
    """Rota web para atualizar configurações de notificações"""
    from flask import redirect, request, url_for

    from db.database import db
    from services.core.profile_service import update_notification_preferences_from_form

    try:
        update_notification_preferences_from_form(current_user, request.form)
        flash("Configurações atualizadas com sucesso!", "success")
        return redirect(url_for("web.profile"))
    except ValueError as err:
        db.session.rollback()
        flash(str(err), "error")
        return redirect(url_for("web.profile"))
    except Exception as exc:
        db.session.rollback()
        logger.exception("Erro ao atualizar configurações: %s", exc)
        flash("Erro ao atualizar configurações", "error")
        return redirect(url_for("web.profile"))


@web_bp.route("/alterar_senha", methods=["POST"])
@login_required
def alterar_senha():
    """Rota web para alterar senha"""
    from flask import redirect, request, url_for

    from db.database import db
    from services.core.profile_service import change_password

    senha_atual = request.form.get("currentPassword") or request.form.get("senha_atual")
    nova_senha = request.form.get("newPassword") or request.form.get("nova_senha")
    confirmar_senha = request.form.get("renewPassword") or request.form.get(
        "confirmar_senha"
    )

    if not all([senha_atual, nova_senha, confirmar_senha]):
        flash("Todos os campos são obrigatórios", "error")
        return redirect(url_for("web.profile"))

    try:
        change_password(current_user, senha_atual, nova_senha, confirmar_senha)
        flash("Senha alterada com sucesso!", "success")
        return redirect(url_for("web.profile"))
    except ValueError as err:
        db.session.rollback()
        flash(str(err), "error")
        return redirect(url_for("web.profile"))
    except Exception as exc:
        db.session.rollback()
        logger.exception("Erro ao alterar senha: %s", exc)
        flash("Erro ao alterar senha", "error")
        return redirect(url_for("web.profile"))


@web_bp.route("/notifications")
@login_required
def notifications():
    """Página de notificações do usuário"""
    return render_app_template("core/notifications.html")


# Rotas removidas - agora são gerenciadas pelos plugins
# As rotas específicas serão registradas pelos plugins através de seus blueprints


@web_bp.errorhandler(404)
def not_found(error):
    return render_app_template("core/notFound.html"), 404


@web_bp.errorhandler(500)
def internal_error(error):
    return render_app_template("core/notFound.html"), 500


@web_bp.route("/notFound")
def not_found_page():
    return render_app_template("core/notFound.html")
