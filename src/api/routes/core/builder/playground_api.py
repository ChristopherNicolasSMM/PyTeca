from flask import Blueprint, jsonify, request
from flask_login import login_required
from utils.permissions import permission_required

playground_api = Blueprint("playground_api", __name__, url_prefix="/api/builder/playground")

@playground_api.route("/proxy", methods=["POST"])
@login_required
@permission_required("admin")
def proxy_request():
    """Placeholder para requisições proxy."""
    return jsonify({"success": False, "error": "Funcionalidade em desenvolvimento"})