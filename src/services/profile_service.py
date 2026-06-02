"""
Regras de negócio relacionadas ao perfil do usuário.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Mapping, MutableMapping, Optional

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from db.database import db
from model.user import User

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def _apply_profile_fields(user: User, data: Mapping[str, Optional[str]]) -> None:
    user.nome_completo = (
        data.get("nome_completo") or data.get("fullName") or user.nome_completo
    )
    user.sobre = data.get("sobre") or data.get("about") or user.sobre
    user.empresa = data.get("empresa") or data.get("company") or user.empresa
    user.cargo = data.get("cargo") or data.get("job") or user.cargo
    user.pais = data.get("pais") or data.get("country") or user.pais
    user.endereco = data.get("endereco") or data.get("address") or user.endereco
    user.telefone = data.get("telefone") or data.get("phone") or user.telefone
    user.twitter = data.get("twitter") or user.twitter
    user.facebook = data.get("facebook") or user.facebook
    user.instagram = data.get("instagram") or user.instagram
    user.linkedin = data.get("linkedin") or user.linkedin


def _save_profile_image(user: User, file: FileStorage) -> None:
    if not file or not file.filename:
        return

    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Tipo de arquivo não permitido. Use png, jpg, jpeg ou gif.")

    filename = secure_filename(f"user_{user.id}_{file.filename}")
    upload_dir = Path(current_app.static_folder) / "uploads" / "profiles"
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / filename
    file.save(destination)

    relative_path = os.path.join("uploads", "profiles", filename)
    user.foto_perfil = relative_path


def update_profile_from_form(
    user: User, form_data: MutableMapping[str, str], files
) -> None:
    _apply_profile_fields(user, form_data)
    if files and "profileImage" in files:
        _save_profile_image(user, files["profileImage"])
    db.session.commit()
    logger.info("Perfil do usuário %s atualizado via formulário.", user.username)


def update_profile_from_json(user: User, payload: Mapping[str, object]) -> None:
    _apply_profile_fields(user, payload)
    db.session.commit()
    logger.info("Perfil do usuário %s atualizado via API JSON.", user.username)


def update_notification_preferences_from_form(
    user: User, form_data: Mapping[str, str]
) -> None:
    user.notificacao_alteracoes = bool(form_data.get("notificacao_alteracoes"))
    user.notificacao_novos_produtos = bool(form_data.get("notificacao_novos_produtos"))
    user.notificacao_ofertas = bool(form_data.get("notificacao_ofertas"))
    user.modo_escuro = bool(form_data.get("modo_escuro"))
    db.session.commit()
    logger.info(
        "Preferências de notificação do usuário %s atualizadas (form).", user.username
    )


def update_notification_preferences_from_json(
    user: User, payload: Mapping[str, object]
) -> None:
    user.notificacao_alteracoes = bool(payload.get("notificacao_alteracoes", False))
    user.notificacao_novos_produtos = bool(
        payload.get("notificacao_novos_produtos", False)
    )
    user.notificacao_ofertas = bool(payload.get("notificacao_ofertas", False))
    db.session.commit()
    logger.info(
        "Preferências de notificação do usuário %s atualizadas (JSON).", user.username
    )


def change_password(
    user: User, senha_atual: str, nova_senha: str, confirmar_senha: str
) -> None:
    if not user.verify_password(senha_atual):
        raise ValueError("Senha atual incorreta.")

    if nova_senha != confirmar_senha:
        raise ValueError("As novas senhas não coincidem.")

    if len(nova_senha) < 6:
        raise ValueError("A senha deve ter pelo menos 6 caracteres.")

    user.password = nova_senha
    db.session.commit()
    logger.info("Senha do usuário %s alterada com sucesso.", user.username)
