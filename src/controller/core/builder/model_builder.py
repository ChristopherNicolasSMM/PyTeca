from flask import Blueprint, render_template
from flask_login import login_required
from utils.permissions import permission_required

model_builder_bp = Blueprint("admin_model_builder", __name__, url_prefix="/admin/model-builder")

@model_builder_bp.route("/")
@login_required
@permission_required("admin")
def index():
    return render_template("core/builder/model_builder.html")