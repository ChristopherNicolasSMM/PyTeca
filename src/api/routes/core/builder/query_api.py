from flask import Blueprint, jsonify, request
from flask_login import login_required
from utils.permissions import permission_required

query_api = Blueprint("query_api", __name__, url_prefix="/api/builder/query")

@query_api.route("/sql", methods=["POST"])
@login_required
@permission_required("admin")
def execute_sql():
    """Placeholder para execução de SQL."""
    return jsonify({"success": False, "error": "Funcionalidade em desenvolvimento"})