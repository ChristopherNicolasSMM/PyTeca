"""
utils/permissions_sync.py — Sincronização código -> banco de Permissions.

"Código lidera, banco segue": este módulo NUNCA é chamado pela UI de Admin
Roles para criar uma Permission do zero. A única fonte de verdade de QUAIS
permissões existem é o código (rotas geradas + anotações @permission nos
models). O banco (tabela `permissions`) é apenas o reflexo runtime disso,
mantido em sincronia automaticamente a cada `generate()`.

A UI de Admin Roles só lê o que já está sincronizado e permite:
  - associar Permission a Role (m:n)
  - atribuir Role a User (m:n)

Camadas cobertas:
  Camada 1 — Rota (automática): toda rota de CRUD gerada ganha uma
             permissão "<plural>.<acao>" correspondente, sem precisar
             de nenhuma anotação explícita no model.
  Camada 2 — Model (@permission): ações de negócio que não mapeiam 1:1
             para uma rota, com associação opcional a um Role.

Ver: docs/manual/05-permissoes.md
"""
from __future__ import annotations

# Ações padrão que toda rota de CRUD gerada sempre tem (Camada 1).
# Mantido em um único lugar para nunca dessincronizar do que o
# controller.py.j2 / routes.py.j2 realmente geram.
_STANDARD_CRUD_ACTIONS = [
    ("list", "Listar"),
    ("detail", "Visualizar detalhe"),
    ("create", "Criar"),
    ("update", "Editar"),
    ("trash", "Mover para lixeira"),
    ("restore", "Restaurar da lixeira"),
    ("delete_permanent", "Excluir permanentemente"),
]


def sync_model_permissions(model_class, plural: str) -> dict:
    """
    Sincroniza permissões da Camada 1 (rotas padrão) e Camada 2
    (@permission no model) para o banco. Idempotente — pode ser chamado
    a cada `generate()` sem criar duplicatas nem apagar associações
    feitas manualmente via UI (Role <-> Permission).

    Retorna um resumo {"created": [...], "existing": [...]} para log.
    """
    from db.database import db
    from model.core.permission import Permission
    from model.core.role import Role
    from annotations import get_permissions_meta

    created, existing = [], []

    # ── Camada 1: permissões automáticas de rota ────────────────────────────
    for action, description in _STANDARD_CRUD_ACTIONS:
        perm_name = f"{plural}.{action}"
        perm = Permission.query.filter_by(name=perm_name).first()
        if perm is None:
            perm = Permission(
                name=perm_name,
                description=f"{description} — {plural}",
            )
            db.session.add(perm)
            created.append(perm_name)
        else:
            existing.append(perm_name)

    # ── Camada 2: permissões de negócio via @permission no model ───────────
    for meta in get_permissions_meta(model_class):
        perm_name = f"{plural}.{meta['action']}"
        perm = Permission.query.filter_by(name=perm_name).first()
        if perm is None:
            perm = Permission(name=perm_name, description=meta["description"])
            db.session.add(perm)
            created.append(perm_name)
        else:
            existing.append(perm_name)
            # Atualiza a descrição se o código mudou (código lidera)
            if meta["description"] and perm.description != meta["description"]:
                perm.description = meta["description"]

        db.session.flush()  # garante perm.id disponível para a associação abaixo

        role_required = meta.get("role_required")
        if role_required:
            role = Role.query.filter_by(name=role_required).first()
            if role is None:
                # Cria o Role automaticamente só se ele realmente não existir —
                # evita que @permission(role_required="x") falhe silenciosamente
                # quando o papel ainda não foi criado pela UI de Admin Roles.
                role = Role(name=role_required, description=f"Criado automaticamente via @permission")
                db.session.add(role)
                db.session.flush()
            if perm not in role.permissions:
                role.permissions.append(perm)

    db.session.commit()

    if created:
        print(f"  🔑 Permissões sincronizadas (novas): {', '.join(created)}")

    return {"created": created, "existing": existing}
