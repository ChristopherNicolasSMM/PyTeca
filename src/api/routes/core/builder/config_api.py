from flask import Blueprint, jsonify, request
from flask_login import login_required
from utils.permissions import permission_required
from services.core.admin.config_service import ConfigService
from model.core.admin.system_config import SystemConfig  # <-- adicionar esta linha

config_api_bp = Blueprint("config_api", __name__, url_prefix="/api/admin/config")

@config_api_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def get_all_configs():
    groups = {}
    all_configs = SystemConfig.query.all()
    for cfg in all_configs:
        groups.setdefault(cfg.group or "geral", []).append({
            "key": cfg.key,
            "value": ConfigService._parse_value(cfg.value, cfg.type),
            "type": cfg.type,
            "description": cfg.description
        })
    return jsonify({"success": True, "groups": groups})

@config_api_bp.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def update_configs():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Nenhum dado enviado"}), 400

    for key, value in data.items():
        cfg = SystemConfig.query.filter_by(key=key).first()
        if cfg:
            ConfigService.set(key, value, type=cfg.type)
        else:
            ConfigService.set(key, value, type="string")

    return jsonify({"success": True, "message": "Configurações salvas"})