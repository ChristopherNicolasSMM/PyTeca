from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from db.database import db
from model.core.builder.model_definition import ModelDefinition
from utils.generate_from_model import generate

# ── Mapeamento de tipos de UI para SQLAlchemy + Python ────────────────────────
_TYPE_MAP = {
    "string":   {"sa": "String(255)", "py": "str"},
    "text":     {"sa": "Text",        "py": "str"},
    "integer":  {"sa": "Integer",     "py": "int"},
    "boolean":  {"sa": "Boolean",     "py": "bool"},
    "datetime": {"sa": "DateTime(timezone=True)", "py": "datetime"},
    "date":     {"sa": "Date",        "py": "date"},
    "float":    {"sa": "Float",       "py": "float"},
}

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class ModelGenerator:
    """
    Gera o arquivo model/.../<nome>.py a partir de uma ModelDefinition
    e, em seguida, encadeia a pipeline completa de geração de CRUD
    (controller, service, routes, templates) via utils.generate_from_model.generate().

    Nada aqui edita controllers/services/templates diretamente — tudo passa
    pelos mesmos .j2 usados pelo restante do projeto, garantindo paridade
    entre models criados manualmente e models criados via UI.
    """

    # ── Validação ───────────────────────────────────────────────────────────

    @classmethod
    def validate_definition(cls, data: dict) -> list[str]:
        """Valida os dados antes de persistir. Retorna lista de erros (vazia = ok)."""
        errors = []

        name = (data.get("name") or "").strip()
        if not name:
            errors.append("Nome do modelo é obrigatório.")
        elif not name[0].isupper():
            errors.append("Nome do modelo deve começar com letra maiúscula (ex: Produto).")
        elif not re.match(r"^[A-Za-z][A-Za-z0-9]*$", name):
            errors.append("Nome do modelo deve conter apenas letras e números, sem espaços.")

        table_name = (data.get("table_name") or "").strip()
        if not table_name:
            errors.append("Nome da tabela é obrigatório.")
        elif not _NAME_RE.match(table_name):
            errors.append("Nome da tabela deve ser snake_case (ex: produtos, minha_tabela).")

        fields = data.get("fields") or []
        if not fields:
            errors.append("Adicione ao menos um campo.")

        seen_names = set()
        for f in fields:
            fname = (f.get("name") or "").strip()
            if not fname:
                errors.append("Há um campo sem nome.")
                continue
            if not _NAME_RE.match(fname):
                errors.append(f"Campo '{fname}' inválido — use snake_case (letras minúsculas, números, _).")
            if fname in seen_names:
                errors.append(f"Campo '{fname}' duplicado.")
            seen_names.add(fname)
            if fname in ("id", "status", "created_at", "updated_at", "trashed_at"):
                errors.append(f"Campo '{fname}' é reservado pelo sistema (gerado automaticamente).")

            # Validação de FK: tabela, coluna-alvo e campo de exibição são
            # obrigatórios e precisam corresponder ao schema real do banco.
            # Sem isso, o model gerado poderia referenciar uma coluna que
            # não existe, ou não é válida como alvo de FK (precisa ser PK
            # ou ter constraint UNIQUE — exigência do próprio SQL, idêntica
            # em SQLite e PostgreSQL).
            ftype = (f.get("type") or "string").lower()
            if ftype == "foreign_key" or f.get("fk_table"):
                fk_table = (f.get("fk_table") or "").strip()
                display_field = (f.get("display_field") or "").strip()
                fk_target_column = (f.get("fk_target_column") or "").strip()

                if not fk_table:
                    errors.append(f"Campo '{fname or '(sem nome)'}': selecione a tabela referenciada.")
                    continue

                from services.core.builder.schema_inspector import SchemaInspector
                info = SchemaInspector.get_table_info(fk_table)
                if info is None:
                    errors.append(f"Campo '{fname}': a tabela '{fk_table}' não existe no banco.")
                    continue

                target_names = {c["name"] for c in info["fk_target_candidates"]}
                if not fk_target_column:
                    # Sem escolha explícita: só é aceitável se houver exatamente
                    # uma candidata (a UI já desabilita o select nesse caso).
                    if len(target_names) != 1:
                        errors.append(
                            f"Campo '{fname}': selecione a coluna-alvo da FK em '{fk_table}' "
                            f"(há {len(target_names)} candidatas válidas: {', '.join(sorted(target_names))})."
                        )
                elif fk_target_column not in target_names:
                    errors.append(
                        f"Campo '{fname}': '{fk_target_column}' não é uma coluna válida como alvo de FK "
                        f"em '{fk_table}' (precisa ser chave primária ou ter UNIQUE). "
                        f"Candidatas: {', '.join(sorted(target_names))}."
                    )

                if not display_field:
                    errors.append(
                        f"Campo '{fname or '(sem nome)'}': selecione o campo de exibição/pesquisa "
                        f"(o que aparece nas listas e na busca — nunca o ID)."
                    )
                else:
                    display_names = {c["name"] for c in info["display_field_candidates"]}
                    if display_field not in display_names:
                        errors.append(
                            f"Campo '{fname}': a coluna '{display_field}' não existe na tabela '{fk_table}'."
                        )

        return errors

    # ── Preparação de contexto ──────────────────────────────────────────────

    @classmethod
    def _default_repr(cls, field_type: str, default) -> str | None:
        """Converte o valor default recebido da UI (sempre string) para literal Python válido."""
        if default in (None, ""):
            return None
        if field_type == "string" or field_type == "text":
            escaped = str(default).replace('"', '\\"')
            return f'"{escaped}"'
        if field_type == "integer":
            try:
                return str(int(default))
            except (TypeError, ValueError):
                return None
        if field_type == "float":
            try:
                return str(float(default))
            except (TypeError, ValueError):
                return None
        if field_type == "boolean":
            return "True" if str(default).lower() in ("true", "1", "sim") else "False"
        return None

    @classmethod
    def _resolve_fk_class_name(cls, fk_table: str, explicit: str | None = None) -> str:
        """
        Resolve o nome da classe Python para uma tabela referenciada por FK.

        Ordem de prioridade:
        1. Nome explícito vindo do payload (se algum dia for enviado)
        2. Nome real do model SQLAlchemy já registrado para essa tabela
           (via db.Model.registry) — sempre correto quando existe
        3. Heurística snake_case -> PascalCase por palavra (fallback para
           tabelas sem model Python ainda mapeado)
        """
        if explicit:
            return explicit
        try:
            from db.database import db
            for mapper in db.Model.registry.mappers:
                if mapper.local_table is not None and mapper.local_table.name == fk_table:
                    return mapper.class_.__name__
        except Exception:
            pass
        words = fk_table.split("_")
        singular_words = [w[:-1] if w.endswith("s") and len(w) > 1 else w for w in words]
        return "".join(w.capitalize() for w in singular_words)

    @classmethod
    def _resolve_fk_target(cls, fk_table: str, fk_target_column: str | None) -> tuple[str, str]:
        """
        Resolve (coluna_alvo, tipo_python) para uma FK.

        - Se `fk_target_column` foi informado, usa-o (já validado em
          validate_definition antes de chegar aqui).
        - Se não foi informado mas só existe UMA candidata válida (o caso
          comum: só o `id`), resolve automaticamente para ela.
        - O tipo Python é inferido a partir do tipo real da coluna no banco
          (ex: Integer para id, String para cpf) — necessário porque uma FK
          para uma coluna UNIQUE de texto não pode ser tipada como int.
        """
        from services.core.builder.schema_inspector import SchemaInspector

        target_column = (fk_target_column or "").strip()
        info = SchemaInspector.get_table_info(fk_table)

        if not target_column:
            candidates = info["fk_target_candidates"] if info else []
            target_column = candidates[0]["name"] if len(candidates) == 1 else "id"

        py_type = "int"
        if info:
            for c in info["fk_target_candidates"]:
                if c["name"] == target_column:
                    col_type = c["type"].upper()
                    if "VARCHAR" in col_type or "TEXT" in col_type or "CHAR" in col_type:
                        py_type = "str"
                    break

        return target_column, py_type

    @classmethod
    def _process_fields(cls, raw_fields: list[dict]) -> list[dict]:
        """
        Processa os campos definidos na UI, preparando o contexto rico
        que o model.py.j2 espera (py_type, type_mapped, default_repr, FK).
        """
        processed = []
        for f in raw_fields:
            ftype = (f.get("type") or "string").lower()
            is_fk = ftype == "foreign_key" or bool(f.get("fk_table"))

            if is_fk:
                fk_table = f.get("fk_table", "").strip()
                fk_class = cls._resolve_fk_class_name(fk_table, f.get("fk_class"))
                fk_target_column, fk_target_py_type = cls._resolve_fk_target(
                    fk_table, f.get("fk_target_column")
                )
                relation_name = f["name"][:-3] if f["name"].endswith("_id") else f["name"]
                processed.append({
                    "name": f["name"] if f["name"].endswith("_id") else f"{f['name']}_id",
                    "is_fk": True,
                    "fk_table": fk_table,
                    "fk_class": fk_class,
                    "fk_relation_name": relation_name,
                    "fk_target_column": fk_target_column,
                    "fk_target_py_type": fk_target_py_type,
                    # Validado como obrigatório em validate_definition() — nunca
                    # mais um fallback hardcoded para "name", que quebrava em
                    # runtime quando a tabela real usava outro nome de coluna.
                    "display_field": (f.get("display_field") or "").strip(),
                    "nullable": f.get("nullable", True),
                })
                continue

            type_info = _TYPE_MAP.get(ftype, _TYPE_MAP["string"])
            processed.append({
                "name": f["name"],
                "is_fk": False,
                "py_type": type_info["py"],
                "type_mapped": type_info["sa"],
                "nullable": f.get("nullable", True),
                "unique": f.get("unique", False),
                "default": f.get("default"),
                "default_repr": cls._default_repr(ftype, f.get("default")),
            })
        return processed

    @classmethod
    def _build_annotations(cls, model_def: ModelDefinition, processed_fields: list[dict]) -> dict:
        """
        Constrói o dict de anotações para o template, preenchendo defaults
        sensatos quando a UI não enviar algo explicitamente (ex: listview
        básico com os 3 primeiros campos, caso o usuário não tenha customizado).
        """
        ann = dict(model_def.annotations or {})
        field_names = [f["name"] for f in processed_fields]

        ann.setdefault("label", model_def.name)
        ann.setdefault("plural", model_def.table_name)

        if "listview" not in ann or not ann["listview"].get("columns"):
            ann["listview"] = {
                "default_sort": field_names[0] if field_names else "id",
                "columns": [
                    {"name": f["name"], "label": f["name"].replace("_", " ").title(), "sortable": not f["is_fk"]}
                    for f in processed_fields[:5]
                ],
                "filters": [],
            }

        if "form" not in ann or not ann["form"].get("fields"):
            ann["form"] = {"fields": field_names, "groups": []}

        if "display_field" not in ann:
            # Usa o primeiro campo string/text como display_field padrão
            first_text = next((f["name"] for f in processed_fields
                                if not f["is_fk"] and f.get("py_type") == "str"), None)
            if first_text:
                ann["display_field"] = first_text

        return ann

    # ── Geração ───────────────────────────────────────────────────────────────

    @classmethod
    def generate_from_definition(cls, model_def_id: int) -> dict:
        model_def = ModelDefinition.query.get(model_def_id)
        if not model_def:
            return {"success": False, "error": "Definição não encontrada."}

        processed_fields = cls._process_fields(model_def.fields or [])
        annotations = cls._build_annotations(model_def, processed_fields)
        field_names = [f["name"] for f in processed_fields]

        template_dir = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "utils" / "generate_model" / "templates" / "standard"
        )
        env = Environment(loader=FileSystemLoader(str(template_dir)), trim_blocks=True, lstrip_blocks=True)
        template = env.get_template("model.py.j2")

        context = {
            "class_name": model_def.name,
            "class_name_lower": model_def.name.lower(),
            "module_name": model_def.module,
            "table_name": model_def.table_name,
            "fields": processed_fields,
            "field_names": field_names,
            "annotations": annotations,
        }

        try:
            code = template.render(context)
        except Exception as e:
            return {"success": False, "error": f"Erro ao renderizar template do modelo: {e}"}

        # Validação de sintaxe antes de gravar no disco — evita deixar o
        # projeto com um arquivo .py inválido que quebraria o próximo import.
        import ast
        try:
            ast.parse(code)
        except SyntaxError as e:
            return {"success": False, "error": f"Modelo gerado tem erro de sintaxe (linha {e.lineno}): {e.msg}"}

        file_path = Path("model") / model_def.module / f"{model_def.name.lower()}.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if file_path.exists():
            return {
                "success": False,
                "error": f"Já existe um arquivo em {file_path}. Use outro nome/módulo ou remova o existente.",
            }

        file_path.write_text(code, encoding="utf-8")

        model_def.generated_file = str(file_path)
        db.session.commit()

        # Encadeia a pipeline completa: controller + service + routes + templates
        try:
            from utils.versioning import start_generation_run
            start_generation_run(model_name=model_def.name, triggered_by="ui:model_builder")
            generate(str(file_path), theme="standard", overwrite=False, add_to_root_menu=True)
        except Exception as e:
            return {
                "success": False,
                "error": f"Model criado em {file_path}, mas a geração do CRUD falhou: {e}",
                "file": str(file_path),
            }

        return {
            "success": True,
            "file": str(file_path),
            "message": (
                f"Modelo '{model_def.name}' e CRUD completo gerados com sucesso. "
                f"Reinicie o servidor para que as novas rotas sejam carregadas."
            ),
        }

    @classmethod
    def preview_code(cls, data: dict) -> dict:
        """
        Renderiza o model.py.j2 SEM salvar no disco — usado pelo botão
        'Pré-visualizar' da UI antes de confirmar a criação.
        """
        errors = cls.validate_definition(data)
        if errors:
            return {"success": False, "errors": errors}

        class _Fake:
            name = data["name"]
            module = data.get("module", "core")
            table_name = data["table_name"]
            fields = data.get("fields", [])
            annotations = data.get("annotations", {})

        processed_fields = cls._process_fields(_Fake.fields)
        annotations = cls._build_annotations(_Fake, processed_fields)

        template_dir = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "utils" / "generate_model" / "templates" / "standard"
        )
        env = Environment(loader=FileSystemLoader(str(template_dir)), trim_blocks=True, lstrip_blocks=True)
        template = env.get_template("model.py.j2")

        context = {
            "class_name": _Fake.name,
            "class_name_lower": _Fake.name.lower(),
            "module_name": _Fake.module,
            "table_name": _Fake.table_name,
            "fields": processed_fields,
            "field_names": [f["name"] for f in processed_fields],
            "annotations": annotations,
        }

        try:
            code = template.render(context)
        except Exception as e:
            return {"success": False, "errors": [f"Erro ao renderizar: {e}"]}

        return {"success": True, "code": code}
