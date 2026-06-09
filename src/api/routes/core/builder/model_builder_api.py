from flask import Blueprint, jsonify, request
from flask_login import login_required
from utils.permissions import permission_required
from model.core.builder.model_definition import ModelDefinition
from services.core.builder.model_generator import ModelGenerator
from db.database import db
model_builder_api = Blueprint("model_builder_api", __name__, url_prefix="/api/core/builder/model")

@model_builder_api.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def list_models():
    models = ModelDefinition.query.all()
    return jsonify({"success": True, "models": [m.__dict__ for m in models]})

@model_builder_api.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create_model():
    data = request.get_json()
    # validações...
    model_def = ModelDefinition(
        name=data["name"],
        module=data.get("module", "core"),
        table_name=data["table_name"],
        fields=data.get("fields", []),
        annotations=data.get("annotations", {})
    )
    db.session.add(model_def)
    db.session.commit()
    return jsonify({"success": True, "id": model_def.id})

@model_builder_api.route("/<int:id>/generate", methods=["POST"])
@login_required
@permission_required("admin")
def generate_model(id):
    result = ModelGenerator.generate_from_definition(id)
    return jsonify(result)