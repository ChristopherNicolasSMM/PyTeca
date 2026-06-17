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
    models = ModelDefinition.query.order_by(ModelDefinition.created_at.desc()).all()
    return _ok({"models": [_model_def_to_dict(m) for m in models]})


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
