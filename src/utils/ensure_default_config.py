"""
Garante que as configurações padrão do sistema existam em SystemConfig,
sem sobrescrever valores que o usuário já tenha alterado manualmente.

Diferente de dev_setup.py (que é exclusivo de ambiente DEV e reseta dados
a cada boot), este módulo roda em QUALQUER ambiente e é estritamente
aditivo: só cria a chave se ela não existir ainda.

Ver: docs/manual/04-versionamento.md
"""
from __future__ import annotations


def ensure_default_system_config() -> None:
    from services.core.admin.config_service import ConfigService
    from model.core.admin.system_config import SystemConfig

    defaults = [
        # ── Versionamento (CodeSnapshot) ────────────────────────────────────
        dict(
            key="versioning.enabled", value=True, type="bool", group="versioning",
            description="Liga/desliga o versionamento automático de arquivos gerados.",
        ),
        dict(
            key="versioning.trigger", value="on_diff", type="string", group="versioning",
            description=(
                "Quando criar um snapshot: always | on_diff | on_overwrite | manual_only. "
                "on_diff (padrão) só versiona quando o conteúdo realmente muda."
            ),
        ),
        dict(
            key="versioning.retention_days", value=0, type="int", group="versioning",
            description="Dias para manter snapshots antigos. 0 = nunca expira (padrão).",
        ),
        dict(
            key="versioning.retention_max_per_file", value=0, type="int", group="versioning",
            description="Máximo de snapshots por arquivo. 0 = ilimitado (padrão).",
        ),
        dict(
            key="versioning.snapshot_on_manual_save", value=True, type="bool", group="versioning",
            description="Versiona também quando um arquivo for salvo pela futura IDE interna.",
        ),
    ]

    for entry in defaults:
        exists = SystemConfig.query.filter_by(key=entry["key"]).first()
        if exists:
            continue  # nunca sobrescreve valor já configurado pelo usuário
        ConfigService.set(
            entry["key"], entry["value"],
            type=entry["type"], group=entry["group"], description=entry["description"],
        )
