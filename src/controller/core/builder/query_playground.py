from flask import Blueprint, render_template
from flask_login import login_required
from utils.permissions import permission_required

query_playground_bp = Blueprint("builder_query", __name__, url_prefix="/builder/query")

@query_playground_bp.route("/")
@login_required
@permission_required("admin")
def index():
    return render_template("core/builder/query_playground.html")