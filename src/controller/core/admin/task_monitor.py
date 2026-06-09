from flask import Blueprint, render_template
from flask_login import login_required
from utils.permissions import permission_required

task_monitor_bp = Blueprint("admin_tasks", __name__, url_prefix="/admin/tasks")

@task_monitor_bp.route("/")
@login_required
@permission_required("admin")
def index():
    return render_template("core/admin/task_monitor.html")