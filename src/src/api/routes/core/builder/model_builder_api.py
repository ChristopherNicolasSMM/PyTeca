from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required

from utils.permissions import permission_required
from model.core.builder.model_definition import ModelDefinition
from services.core.builder.model_generator import ModelGenerator
from db.database import db

model_builder_api = Blueprint(
    "model_builder_api", __name__, url_prefix="/api/core/builder/model"
)


def _ok(data=None, code=200):
    return jsonify({"success": True, **(data or {})}), code


def _err(message, code=400, **extra):
    return jsonify({"success": False, "error": message, **extra}), code


def _model_def_to_dict(m: ModelDefinition) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "module": m.module,
        "table_name": m.table_name,
        "fields": m.fields,
        "annotations": m.annotations,
        "generated_file": m.generated_file,
        "active": m.active,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


# ── Listagem ────────────────────────────────────────────────────────────────

@model_builder_api.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def list_models():
    """
    Lista definições, com filtros opcionais via query string:
      ?module=bookstore       — filtra por módulo exato
      ?search=produto         — busca por nome ou nome de tabela (case-insensitive)
      ?group_by=module        — agrupa o resultado por módulo (ver formato abaixo)

    Sem group_by, retorna {"models": [...]} (lista plana, comportamento anterior).
    Com group_by=module, retorna {"groups": [{"module": "...", "models": [...]}]}.
    """
    query = ModelDefinition.query

    module_filter = (request.args.get("module") or "").strip()
    if module_filter:
        query = query.filter(ModelDefinition.module == module_filter)

    search = (request.args.get("search") or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(ModelDefinition.name.ilike(like), ModelDefinition.table_name.ilike(like))
        )

    models = query.order_by(ModelDefinition.created_at.desc()).all()

    group_by = (request.args.get("group_by") or "").strip()
    if group_by == "module":
        grouped: dict[str, list] = {}
        for m in models:
            grouped.setdefault(m.module, []).append(_model_def_to_dict(m))
        groups = [
            {"module": mod, "models": items}
            for mod, items in sorted(grouped.items())
        ]
        return _ok({"groups": groups})

    return _ok({"models": [_model_def_to_dict(m) for m in models]})


@model_builder_api.route("/modules", methods=["GET"])
@login_required
@permission_required("admin")
def list_distinct_modules():
    """
    SELECT DISTINCT module — popula o combobox de filtro por módulo na UI,
    sempre refletindo os módulos que de fato existem nas definições salvas.
    """
    rows = db.session.query(ModelDefinition.module).distinct().order_by(ModelDefinition.module).all()
    modules = [r[0] for r in rows if r[0]]
    return _ok({"modules": modules})


@model_builder_api.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("admin")
def get_model(id: int):
    m = ModelDefinition.query.get(id)
    if not m:
        return _err("Definição não encontrada.", 404)
    return _ok({"model": _model_def_to_dict(m)})


# ── Validação e Preview (sem persistir nada) ──────────────────────────────────

@model_builder_api.route("/validate", methods=["POST"])
@login_required
@permission_required("admin")
def validate_model():
    data = request.get_json(silent=True) or {}
    errors = ModelGenerator.validate_definition(data)
    return _ok({"valid": not errors, "errors": errors})


@model_builder_api.route("/preview", methods=["POST"])
@login_required
@permission_required("admin")
def preview_model():
    data = request.get_json(silent=True) or {}
    result = ModelGenerator.preview_code(data)
    if not result["success"]:
        return _err("Não foi possível gerar a pré-visualização.", 422, errors=result.get("errors", []))
    return _ok({"code": result["code"]})


# ── Criação ───────────────────────────────────────────────────────────────────

@model_builder_api.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create_model():
    data = request.get_json(silent=True) or {}

    errors = ModelGenerator.validate_definition(data)
    if errors:
        return _err("Dados inválidos.", 422, errors=errors)

    if ModelDefinition.query.filter_by(name=data["name"]).first():
        return _err(f"Já existe um modelo chamado '{data['name']}'.", 409)
    if ModelDefinition.query.filter_by(table_name=data["table_name"]).first():
        return _err(f"Já existe um modelo usando a tabela '{data['table_name']}'.", 409)

    model_def = ModelDefinition(
        name=data["name"],
        module=data.get("module", "core").strip() or "core",
        table_name=data["table_name"],
        fields=data.get("fields", []),
        annotations=data.get("annotations", {}),
    )
    db.session.add(model_def)
    db.session.commit()
    return _ok({"id": model_def.id, "model": _model_def_to_dict(model_def)}, 201)


@model_builder_api.route("/<int:id>/generate", methods=["POST"])
@login_required
@permission_required("admin")
def generate_model(id: int):
    result = ModelGenerator.generate_from_definition(id)
    if not result.get("success"):
        return jsonify(result), 422
    return jsonify(result)


@model_builder_api.route("/<int:id>", methods=["DELETE"])
@login_required
@permission_required("admin")
def delete_model_definition(id: int):
    """
    Remove apenas o REGISTRO da definição (não apaga arquivos já gerados
    no disco — isso continua sendo uma ação manual e intencional do
    desenvolvedor, em linha com a regra do projeto de nunca apagar
    código gerado automaticamente sem confirmação explícita).
    """
    m = ModelDefinition.query.get(id)
    if not m:
        return _err("Definição não encontrada.", 404)
    db.session.delete(m)
    db.session.commit()
    return _ok({"message": "Definição removida. Arquivos já gerados no disco não foram apagados."})


# ── Introspecção de tabelas/colunas (para configuração de FK na UI) ───────────
# Resolve dois problemas: (1) tabela referenciada era texto livre sem
# validação; (2) display_field e coluna-alvo da FK eram hardcoded/sempre
# a PK, quebrando em runtime sempre que a tabela real usava outro nome de
# coluna de texto, ou quando se queria referenciar uma chave alternativa
# (ex: CPF com unique=True) em vez do id.

@model_builder_api.route("/tables", methods=["GET"])
@login_required
@permission_required("admin")
def list_tables():
    """Lista as tabelas existentes no banco (introspecção real do schema)."""
    from services.core.builder.schema_inspector import SchemaInspector
    tables = SchemaInspector.list_tables()
    return _ok({"tables": tables})


@model_builder_api.route("/tables/<string:table_name>", methods=["GET"])
@login_required
@permission_required("admin")
def get_table_detail(table_name: str):
    """
    Retorna, para a tabela escolhida:
      - fk_target_candidates: colunas válidas como alvo de FK (PK + UNIQUE).
        A UI desabilita o select quando há só uma candidata (o caso comum: só o id).
      - display_field_candidates: colunas sugeridas para exibição/pesquisa.
    """
    from services.core.builder.schema_inspector import SchemaInspector
    info = SchemaInspector.get_table_info(table_name)
    if info is None:
        return _err(f"Tabela '{table_name}' não encontrada.", 404)
    return _ok(info)
