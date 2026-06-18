from flask import Blueprint, render_template
from flask_login import login_required
from utils.permissions import permission_required

admin_roles_bp = Blueprint("admin_roles", __name__, url_prefix="/admin/roles")


@admin_roles_bp.route("/")
@login_required
@permission_required("admin")
def index():
    return render_template("core/admin/roles.html")
