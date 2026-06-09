from flask import Blueprint, render_template
from flask_login import login_required
from utils.permissions import permission_required

config_bp = Blueprint("admin_config", __name__, url_prefix="/admin/config")

@config_bp.route("/")
@login_required
@permission_required("admin")
def index():
    return render_template("core/admin/config.html")