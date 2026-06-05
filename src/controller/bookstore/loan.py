from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from model.loan import Loan, LoanStatus
from model.user_layout_pref import UserLayoutPref
from services.loan.loan_service import LoanService
from utils.smart_list import ColumnDef, FilterDef, SmartListConfig, SmartListRenderer
from utils.smart_list.export import export_csv, export_excel, export_pdf

loan_bp = Blueprint("loans", __name__, url_prefix="/loans")

# ── Configuração SmartList ────────────────────────────────────────────────────

SMART_LIST_CONFIG = SmartListConfig(
    list_id="loans",
    endpoint="loans.list",
    columns=[
        ColumnDef("id", "ID", sortable=True, width="60px", align="start"),
        ColumnDef("user.username", "Usuário", sortable=True, width=None, align="start"),
        ColumnDef("book.title", "Livro", sortable=True, width=None, align="start"),
        ColumnDef("loan_date", "Data Empréstimo", sortable=False, width="120px", align="center"),
        ColumnDef("due_date", "Data Devolução", sortable=False, width="120px", align="center"),
        ColumnDef("status", "Status", sortable=False, width="100px", align="center")
    ],
    filters=[
        FilterDef("status", "status", type="select"),
        FilterDef("search", "search", type="text", placeholder="Usuário ou livro...")
    ],
    default_sort="-loan_date",
    default_dir="asc",
    page_sizes=[10, 20, 50, 100],
    default_page_size=20,
    exportable=True,
    export_filename="loans",
)


# ── Listagem ──────────────────────────────────────────────────────────────────

@loan_bp.route("/")
@login_required
def list():
    status = request.args.get("status", LoanStatus.ACTIVE.value)
    export = request.args.get("export", "")

    user_layout = None
    if current_user.is_authenticated:
        pref = UserLayoutPref.get_for_user(current_user.id, SMART_LIST_CONFIG.list_id)
        if pref:
            user_layout = pref.layout

    per_page = int(request.args.get(
        "per_page",
        (user_layout or {}).get("per_page", SMART_LIST_CONFIG.default_page_size),
    ))

    service = LoanService()
    result = service.list(
        page=int(request.args.get("page", 1)),
        per_page=per_page,
        status=status,
        search=request.args.get("search", "").strip() or None,
        sort=request.args.get("sort", SMART_LIST_CONFIG.default_sort),
        direction=request.args.get("dir", SMART_LIST_CONFIG.default_dir),
    )

    if export in ("csv", "excel", "pdf"):
        all_result = service.list(page=1, per_page=10_000, status=status)
        visible_cols = (user_layout or {}).get("columns") or None
        if export == "csv":
            return export_csv(SMART_LIST_CONFIG, all_result.items, visible_cols)
        if export == "excel":
            return export_excel(SMART_LIST_CONFIG, all_result.items, visible_cols)
        if export == "pdf":
            return export_pdf(SMART_LIST_CONFIG, all_result.items, visible_cols, title="Empréstimoss")

    renderer = SmartListRenderer(SMART_LIST_CONFIG)
    sl = renderer.build_context(
        items=result.items,
        total=result.total,
        pages=result.pages,
        user_layout=user_layout,
    )

    return render_template(
        "loans/manage.html",
        sl=sl,
        counts=service.count_by_status(),
        current_status=status,
    )


# ── Detalhe ───────────────────────────────────────────────────────────────────

@loan_bp.route("/<int:item_id>")
@login_required
def detail(item_id: int):
    service = LoanService()
    item = service.get_by_id(item_id)
    if not item:
        abort(404)
    return render_template("loans/detail.html", loan=item)


# ── Ações POST ────────────────────────────────────────────────────────────────

@loan_bp.route("/<int:loan_id>/trash", methods=["POST"])
@login_required
def trash(loan_id: int):
    service = LoanService()
    r = service.trash(loan_id)
    flash("Movido para a lixeira." if r.success else r.error,
          "success" if r.success else "danger")
    return redirect(request.referrer or url_for("loans.list"))


@loan_bp.route("/<int:loan_id>/restore", methods=["POST"])
@login_required
def restore(loan_id: int):
    service = LoanService()
    r = service.restore(loan_id)
    flash("Registro restaurado." if r.success else r.error,
          "success" if r.success else "danger")
    return redirect(request.referrer or url_for("loans.list", status="trash"))


@loan_bp.route("/<int:loan_id>/delete", methods=["POST"])
@login_required
def delete_permanent(loan_id: int):
    if not current_user.is_admin:
        abort(403)
    service = LoanService()
    r = service.delete_permanent(loan_id)
    flash("Excluído permanentemente." if r.success else r.error,
          "success" if r.success else "danger")
    return redirect(url_for("loans.list", status="trash"))


@loan_bp.route("/<int:loan_id>/discard", methods=["POST"])
@login_required
def discard_draft(loan_id: int):
    service = LoanService()
    r = service.discard_draft(loan_id)
    flash("Rascunho descartado." if r.success else r.error,
          "info" if r.success else "danger")
    return redirect(url_for("loans.list"))
