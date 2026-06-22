"""
utils/versioning.py — Sistema de versionamento de arquivos gerados/editados.

Ponto único de decisão sobre QUANDO versionar (consulta SystemConfig via
ConfigService) e COMO versionar (grava CodeSnapshot, mantém is_current em
sincronia, agrupa por generation_run_id).

Nenhum .j2 conhece esse módulo — a integração acontece em um único lugar:
utils/generate_from_model._write_file(). Isso mantém os templates 100%
alheios a versionamento, como qualquer outra peça de infraestrutura.

Ver: docs/manual/04-versionamento.md
"""
from __future__ import annotations

import hashlib
import uuid
from contextvars import ContextVar
from typing import Optional

from db.database import db
from model.core.admin.code_snapshot import CodeSnapshot, SnapshotOrigin

# ── Contexto da execução atual (thread-safe, não usa estado de módulo) ───────
# Definido uma vez no início de _run_generation() e lido por todo write
# subsequente daquela mesma execução, sem precisar mudar a assinatura de
# generate_controller/generate_service/etc.
_current_run_id: ContextVar[Optional[str]] = ContextVar("_current_run_id", default=None)
_current_model_name: ContextVar[Optional[str]] = ContextVar("_current_model_name", default=None)
_current_triggered_by: ContextVar[Optional[str]] = ContextVar("_current_triggered_by", default=None)


def start_generation_run(model_name: str | None, triggered_by: str = "cli:generate") -> str:
    """
    Marca o início de uma execução de geração. Todos os arquivos escritos
    até o próximo start_generation_run() (ou fim do processo) compartilham
    o mesmo generation_run_id — permite agrupar "5 arquivos gerados juntos"
    numa única entrada de histórico na futura tela de versionamento.
    """
    run_id = str(uuid.uuid4())
    _current_run_id.set(run_id)
    _current_model_name.set(model_name)
    _current_triggered_by.set(triggered_by)
    return run_id


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _get_config():
    """Import tardio para evitar dependência circular (ConfigService -> db -> ...)."""
    from services.core.admin.config_service import ConfigService
    return ConfigService


def snapshot_if_needed(
    file_path: str,
    new_content: str,
    *,
    origin: str = SnapshotOrigin.GENERATED,
    created_by_user_id: int | None = None,
) -> CodeSnapshot | None:
    """
    Decide, com base em SystemConfig (chaves versioning.*), se deve
    versionar esta escrita, e grava se aplicável.

    Chamado de um único lugar: utils.generate_from_model._write_file(),
    SEMPRE ANTES de path.write_text() sobrescrever o arquivo no disco.

    IMPORTANTE — captura de edições manuais perdidas: o histórico só
    conhece o que passou por esta função. Se alguém editar um arquivo
    gerado diretamente no disco (fora do gerador) e depois rodar
    `generate --overwrite`, essa edição manual nunca teria sido
    registrada — o sistema compararia o novo conteúdo gerado com o
    último snapshot do BANCO, que não sabe da edição manual, e
    concluiria (corretamente, dado o que sabia) que nada mudou.
    Resultado: a edição manual se perde sem nunca aparecer no histórico.

    Para evitar isso, ANTES de decidir sobre o novo conteúdo, esta
    função lê o conteúdo ATUAL do disco (se o arquivo já existir) e,
    se ele divergir do último snapshot conhecido, captura essa versão
    primeiro (origin=PRE_OVERWRITE) — preservando a edição manual no
    histórico antes de ela ser sobrescrita.

    Retorna o CodeSnapshot do novo conteúdo, ou None se nada foi
    versionado para ele (trigger desabilitado, ou on_diff sem alteração
    real) — independente de uma captura PRE_OVERWRITE ter ocorrido.
    """
    Config = _get_config()

    if not Config.get("versioning.enabled", default=True):
        return None

    trigger = Config.get("versioning.trigger", default="on_diff")
    if trigger == "manual_only":
        return None

    last = (
        CodeSnapshot.query
        .filter_by(file_path=file_path, is_current=True)
        .order_by(CodeSnapshot.created_at.desc())
        .first()
    )

    # ── Captura de edição manual perdida (antes de qualquer outra decisão) ──
    from pathlib import Path
    disk_path = Path(file_path)
    if disk_path.exists():
        try:
            disk_content = disk_path.read_text(encoding="utf-8")
            disk_hash = _sha256(disk_content)
            if last is None or last.content_hash != disk_hash:
                # O disco tem algo que o histórico não conhece — é uma
                # edição manual (ou a primeira vez que este arquivo entra
                # no sistema de versionamento). Captura antes de prosseguir.
                if last is not None:
                    last.is_current = False
                manual_snap = CodeSnapshot(
                    file_path=file_path,
                    content=disk_content,
                    content_hash=disk_hash,
                    size_bytes=len(disk_content.encode("utf-8")),
                    origin=SnapshotOrigin.PRE_OVERWRITE,
                    triggered_by="auto:pre_overwrite_capture",
                    generation_run_id=_current_run_id.get(),
                    is_current=True,
                    parent_snapshot_id=last.id if last is not None else None,
                )
                db.session.add(manual_snap)
                db.session.commit()
                last = manual_snap  # a comparação seguinte usa esta como "última"
        except (UnicodeDecodeError, OSError):
            pass  # arquivo binário ou ilegível — não tenta versionar o disco

    new_hash = _sha256(new_content)

    if trigger == "on_diff" and last is not None and last.content_hash == new_hash:
        return None  # conteúdo idêntico ao último — nada para versionar

    if trigger == "on_overwrite" and last is None:
        # Primeira vez que este arquivo é criado — não é "overwrite" ainda.
        # Ainda assim, guardamos a primeira versão como baseline, senão um
        # "on_overwrite" futuro não teria com o que comparar/restaurar.
        pass

    if last is not None:
        last.is_current = False  # a nova escrita passa a ser a corrente

    snapshot = CodeSnapshot(
        file_path=file_path,
        content=new_content,
        content_hash=new_hash,
        size_bytes=len(new_content.encode("utf-8")),
        origin=origin,
        triggered_by=_current_triggered_by.get(),
        model_name=_current_model_name.get(),
        generation_run_id=_current_run_id.get(),
        is_current=True,
        parent_snapshot_id=last.id if last is not None else None,
        created_by_user_id=created_by_user_id,
    )
    db.session.add(snapshot)
    db.session.commit()
    return snapshot


def cleanup_old_snapshots() -> int:
    """
    Aplica a política de retenção configurada em SystemConfig:
    - versioning.retention_days (0 = nunca expira por idade)
    - versioning.retention_max_per_file (0 = ilimitado por arquivo)

    Por padrão (instalação nova) ambos são 0 — nada é apagado automaticamente,
    conforme decisão de produto: "por padrão não apaga".

    Retorna a quantidade de snapshots removidos. Pensado para ser chamado
    por um job do APScheduler já existente, não por um novo scheduler.
    """
    Config = _get_config()
    retention_days = Config.get("versioning.retention_days", default=0)
    retention_max = Config.get("versioning.retention_max_per_file", default=0)

    removed = 0

    if retention_days and retention_days > 0:
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        old = (
            CodeSnapshot.query
            .filter(CodeSnapshot.created_at < cutoff)
            .filter(CodeSnapshot.is_current.is_(False))  # nunca apaga a versão corrente
            .all()
        )
        for s in old:
            db.session.delete(s)
            removed += 1

    if retention_max and retention_max > 0:
        # Para cada file_path com mais de N snapshots, remove os excedentes
        # (mais antigos primeiro), preservando sempre o is_current=True.
        paths = [r[0] for r in db.session.query(CodeSnapshot.file_path).distinct().all()]
        for path in paths:
            snapshots = (
                CodeSnapshot.query
                .filter_by(file_path=path)
                .order_by(CodeSnapshot.created_at.desc())
                .all()
            )
            excess = snapshots[retention_max:]
            for s in excess:
                if not s.is_current:
                    db.session.delete(s)
                    removed += 1

    if removed:
        db.session.commit()
    return removed
