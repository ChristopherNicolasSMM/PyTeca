"""
services/core/builder/schema_inspector.py — Introspecção de schema real
do banco, usada pelo Model Builder para popular:
  1. O select de "Tabela referenciada" ao configurar uma FK
  2. O select de "Coluna alvo da FK" — PK por padrão, mas também aceita
     qualquer coluna com constraint UNIQUE (ex: CPF), que é exatamente o
     que SQL exige nativamente para ser destino válido de FOREIGN KEY —
     suportado de forma idêntica em SQLite e PostgreSQL, sem nenhuma
     anotação especial além do unique=True que o Model Builder já gera.
  3. O select de "Campo de exibição/pesquisa" — sugestão de colunas de
     texto para exibir em listas/dropdowns no lugar do ID.

Por que isso existe: antes desta correção, o usuário digitava o nome da
tabela referenciada em texto livre e o sistema sempre assumia a PK como
alvo da FK e display_field="name" — quebrando em runtime sempre que a
tabela real usava outro nome de coluna, e sem permitir referenciar uma
chave alternativa (ex: FK por CPF em vez de por id).

Usa sqlalchemy.inspect(db.engine) — funciona sobre o SCHEMA REAL do banco,
não sobre a lista de models Python carregados. Cobre tanto tabelas geradas
pelo CrudGen quanto qualquer tabela criada por fora dele.

Ver: docs/manual/08-model-builder-fk.md
"""
from __future__ import annotations

# Colunas que nunca são boas candidatas a display_field — são metadados
# de sistema, não algo que identifique o registro para um humano.
_EXCLUDED_DISPLAY_NAMES = {
    "id", "status", "created_at", "updated_at", "trashed_at",
    "password_hash", "is_admin", "is_active",
}

# Nomes de coluna fortes candidatos a display_field, em ordem de preferência
# — usado só para ORDENAR sugestões, nunca para escolher sem confirmação.
_PREFERRED_DISPLAY_NAMES = ["name", "nome", "titulo", "title", "descricao", "description", "label", "nome_completo"]


class SchemaInspector:
    """Leitura somente-leitura do schema do banco — nunca migra nem altera nada."""

    @classmethod
    def list_tables(cls) -> list[dict]:
        """Lista todas as tabelas existentes no banco, com contagem de colunas."""
        from sqlalchemy import inspect
        from db.database import db

        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()

        result = []
        for name in sorted(table_names):
            columns = inspector.get_columns(name)
            result.append({"name": name, "column_count": len(columns)})
        return result

    @classmethod
    def get_table_info(cls, table_name: str) -> dict | None:
        """
        Retorna, para uma tabela:
          - `fk_target_candidates`: colunas válidas como ALVO de uma FK
            (PK + colunas com UNIQUE) — auto-disable na UI quando só há uma.
          - `display_field_candidates`: colunas sugeridas para exibição/busca.

        Retorna None se a tabela não existir.
        """
        from sqlalchemy import inspect
        from db.database import db

        inspector = inspect(db.engine)
        if table_name not in inspector.get_table_names():
            return None

        raw_columns = inspector.get_columns(table_name)
        pk_columns = set(inspector.get_pk_constraint(table_name).get("constrained_columns", []))

        # Colunas com constraint UNIQUE (índices únicos) — é exatamente o
        # que SQL exige para ser alvo de FOREIGN KEY além da PK. Funciona
        # de forma idêntica em SQLite e PostgreSQL.
        unique_columns: set[str] = set()
        for idx in inspector.get_unique_constraints(table_name):
            unique_columns.update(idx.get("column_names", []))
        # Alguns bancos (SQLite incluso) expõem UNIQUE como índice único
        # em vez de "unique constraint" — cobre os dois casos.
        for idx in inspector.get_indexes(table_name):
            if idx.get("unique"):
                unique_columns.update(idx.get("column_names", []))

        fk_columns = {
            col
            for fk in inspector.get_foreign_keys(table_name)
            for col in fk.get("constrained_columns", [])
        }

        fk_target_candidates = []
        display_field_candidates = []

        for col in raw_columns:
            col_name = col["name"]
            col_type = str(col["type"])
            is_pk = col_name in pk_columns
            is_unique = col_name in unique_columns
            is_text = "VARCHAR" in col_type.upper() or "TEXT" in col_type.upper()

            if is_pk or is_unique:
                fk_target_candidates.append({
                    "name": col_name,
                    "type": col_type,
                    "is_pk": is_pk,
                    "is_unique": is_unique,
                })

            is_excluded_display = (
                col_name in _EXCLUDED_DISPLAY_NAMES or col_name in fk_columns
            )
            display_field_candidates.append({
                "name": col_name,
                "type": col_type,
                "is_pk": is_pk,
                "is_fk": col_name in fk_columns,
                "suggested_display_field": is_text and not is_excluded_display,
            })

        # PK sempre primeiro na lista de alvo de FK (é o padrão esperado)
        fk_target_candidates.sort(key=lambda c: (0 if c["is_pk"] else 1, c["name"]))

        def display_sort_key(c):
            if not c["suggested_display_field"]:
                return (1, c["name"])
            try:
                pref_idx = _PREFERRED_DISPLAY_NAMES.index(c["name"].lower())
            except ValueError:
                pref_idx = len(_PREFERRED_DISPLAY_NAMES)
            return (0, pref_idx, c["name"])

        display_field_candidates.sort(key=display_sort_key)

        return {
            "table": table_name,
            "fk_target_candidates": fk_target_candidates,
            "display_field_candidates": display_field_candidates,
        }

    @classmethod
    def list_columns(cls, table_name: str) -> list[dict] | None:
        """
        Mantido por compatibilidade com chamadas existentes — retorna só
        as colunas com `suggested_display_field`, sem a parte de FK target.
        Prefira `get_table_info()` para código novo.
        """
        info = cls.get_table_info(table_name)
        return info["display_field_candidates"] if info else None
