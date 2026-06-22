"""
services/core/admin/snapshot_service.py — Camada de leitura e operações
sobre o histórico de versionamento (CodeSnapshot).

Esta é a peça que faltava desde o fix16: o schema já existia pronto para
diff/restauração (conteúdo completo + parent_snapshot_id), mas nenhuma
API ou tela consumia isso. Aqui fechamos o ciclo.

Função do PyTeca aqui é estritamente "recuperar e comparar versões" — a
edição de fato do arquivo (escrever código novo) fica para o code-server,
fora da aplicação. Ver docs/setup/code-server.md.
"""
from __future__ import annotations

import difflib
from datetime import datetime, timezone

from db.database import db
from model.core.admin.code_snapshot import CodeSnapshot, SnapshotOrigin


class SnapshotService:

    @classmethod
    def list_files(cls, search: str | None = None) -> list[dict]:
        """
        Lista, para cada file_path distinto, a versão atual (is_current=True)
        com metadados resumidos — usado para popular a lista lateral de
        "arquivos com histórico" na tela.
        """
        query = CodeSnapshot.query.filter_by(is_current=True)
        if search:
            query = query.filter(CodeSnapshot.file_path.ilike(f"%{search}%"))

        current_snapshots = query.order_by(CodeSnapshot.file_path).all()

        result = []
        for snap in current_snapshots:
            version_count = (
                CodeSnapshot.query.filter_by(file_path=snap.file_path).count()
            )
            result.append({
                "file_path": snap.file_path,
                "current_snapshot_id": snap.id,
                "version_count": version_count,
                "last_modified": snap.created_at.isoformat() if snap.created_at else None,
                "last_origin": snap.origin,
                "model_name": snap.model_name,
            })
        return result

    @classmethod
    def get_history(cls, file_path: str) -> list[dict]:
        """
        Retorna o histórico completo de um arquivo, mais recente primeiro,
        cada entrada já com o `to_dict()` do snapshot — sem o `content`
        (que pode ser grande; só é buscado sob demanda no diff/preview).
        """
        snapshots = (
            CodeSnapshot.query
            .filter_by(file_path=file_path)
            .order_by(CodeSnapshot.created_at.desc())
            .all()
        )
        return [s.to_dict() for s in snapshots]

    @classmethod
    def get_content(cls, snapshot_id: int) -> dict | None:
        """Retorna o conteúdo completo de um snapshot específico (para preview isolado)."""
        snap = CodeSnapshot.query.get(snapshot_id)
        if not snap:
            return None
        d = snap.to_dict()
        d["content"] = snap.content
        return d

    @classmethod
    def diff(cls, snapshot_id_a: int, snapshot_id_b: int) -> dict | None:
        """
        Gera um diff unificado (formato compatível com `git diff` / patch)
        entre dois snapshots — qualquer ordem cronológica é aceita, mas a
        convenção é A = mais antigo, B = mais novo, refletida nos cabeçalhos.

        Retorna None se algum dos dois snapshots não existir, ou se forem
        de file_path diferentes (comparar arquivos diferentes não faz
        sentido nesta tela — diff é sempre entre versões do MESMO arquivo).
        """
        snap_a = CodeSnapshot.query.get(snapshot_id_a)
        snap_b = CodeSnapshot.query.get(snapshot_id_b)
        if not snap_a or not snap_b:
            return None
        if snap_a.file_path != snap_b.file_path:
            return None

        lines_a = snap_a.content.splitlines(keepends=True)
        lines_b = snap_b.content.splitlines(keepends=True)

        label_a = f"{snap_a.file_path} ({snap_a.created_at.strftime('%d/%m/%Y %H:%M')})"
        label_b = f"{snap_b.file_path} ({snap_b.created_at.strftime('%d/%m/%Y %H:%M')})"

        unified = "".join(difflib.unified_diff(
            lines_a, lines_b, fromfile=label_a, tofile=label_b, lineterm="\n",
        ))

        identical = snap_a.content_hash == snap_b.content_hash

        return {
            "file_path": snap_a.file_path,
            "snapshot_a": snap_a.to_dict(),
            "snapshot_b": snap_b.to_dict(),
            "identical": identical,
            "unified_diff": unified,
        }

    @classmethod
    def restore(cls, snapshot_id: int, *, write_to_disk: bool = True,
                created_by_user_id: int | None = None) -> dict:
        """
        Restaura uma versão antiga: grava o conteúdo dela de volta no
        arquivo real (se `write_to_disk=True`) e cria um NOVO snapshot
        com origin=RESTORE — a restauração nunca é silenciosa, ela
        mesma entra no histórico, encadeada à versão que era corrente
        antes da restauração (parent_snapshot_id).

        Por padrão grava no disco — é o objetivo prático da tela
        ("recuperar uma versão anterior"). Pode ser chamado com
        write_to_disk=False para um cenário futuro de "só registrar
        a intenção sem tocar o arquivo agora", mas não há tela hoje
        para esse caso.
        """
        from pathlib import Path
        import hashlib

        old = CodeSnapshot.query.get(snapshot_id)
        if not old:
            return {"success": False, "error": "Snapshot não encontrado."}

        current = (
            CodeSnapshot.query
            .filter_by(file_path=old.file_path, is_current=True)
            .order_by(CodeSnapshot.created_at.desc())
            .first()
        )

        if current and current.id == old.id:
            return {"success": False, "error": "Esta já é a versão atual — nada para restaurar."}

        if write_to_disk:
            try:
                path = Path(old.file_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(old.content, encoding="utf-8")
            except Exception as e:
                return {"success": False, "error": f"Falha ao escrever no disco: {e}"}

        if current:
            current.is_current = False

        new_hash = hashlib.sha256(old.content.encode("utf-8")).hexdigest()
        restored = CodeSnapshot(
            file_path=old.file_path,
            content=old.content,
            content_hash=new_hash,
            size_bytes=len(old.content.encode("utf-8")),
            origin=SnapshotOrigin.RESTORE,
            triggered_by="ui:snapshot_viewer",
            model_name=old.model_name,
            is_current=True,
            parent_snapshot_id=current.id if current else old.id,
            created_by_user_id=created_by_user_id,
        )
        db.session.add(restored)
        db.session.commit()

        return {
            "success": True,
            "message": f"Versão de {old.created_at.strftime('%d/%m/%Y %H:%M')} restaurada com sucesso.",
            "snapshot": restored.to_dict(),
        }
