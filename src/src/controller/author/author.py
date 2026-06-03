from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from model.author import Author, AuthorStatus
from model.user_layout_pref import UserLayoutPref
from services.author.author_service import AuthorService
from utils.smart_list import ColumnDef, FilterDef, SmartListConfig, SmartListRenderer
from utils.smart_list.export import export_csv, export_excel, export_pdf

bp = Blueprint("authors", __name__, url_prefix="/authors")

# ---- Configuração SmartList ----
def _genre_options():
    return [("", "Todos")]

SMART_LIST_CONFIG = SmartListConfig(
    list_id="authors",
    endpoint="authors.list",
    columns=[
                ColumnDef("id", "ID", sortable=True, width="60px", align="start"),
        ColumnDef("name", "Nome", sortable=True, width="None", align="start"),
        ColumnDef("birth_year", "Ano Nascimento", sortable=False, width="100px", align="center")
    ],
    filters=[
                FilterDef("name", "name", type="text", placeholder="Buscar por nome...")
    ],
    default_sort="name",
    default_dir="asc",
    page_sizes=[10, 20, 50, 100],
    default_page_size=20,
    exportable=True,
    export_filename="authors",
)

@bp.route("/")
@login_required
def list():
    status = request.args.get("status", "AuthorStatus.ACTIVE")
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

    service = AuthorService()
    result = service.list(
        page=int(request.args.get("page", 1)),
        per_page=per_page,
        status=status,
        search=request.args.get("search", "").strip() or None,
        genre=request.args.get("genre", "").strip() or None,
        sort=request.args.get("sort", SMART_LIST_CONFIG.default_sort),
        direction=request.args.get("dir", SMART_LIST_CONFIG.default_dir),
    )

    if export in ("csv", "excel", "pdf"):
        all_result = service.list(page=1, per_page=10_000, status=status, ...)
        visible_cols = (user_layout or {}).get("columns") or None
        if export == "csv":
            return export_csv(SMART_LIST_CONFIG, all_result.items, visible_cols)
        if export == "excel":
            return export_excel(SMART_LIST_CONFIG, all_result.items, visible_cols)
        if export == "pdf":
            return export_pdf(SMART_LIST_CONFIG, all_result.items, visible_cols, title="Autoress")

    renderer = SmartListRenderer(SMART_LIST_CONFIG)
    sl = renderer.build_context(
        items=result.items,
        total=result.total,
        pages=result.pages,
        user_layout=user_layout,
    )

    return render_template(
        "authors/manage.html",
        sl=sl,
        counts=service.count_by_status(),
        current_status=status,
    )

@bp.route("/<int:item_id>")
@login_required
def detail(item_id: int):
    service = AuthorService()
    item = service.get_by_id(item_id)
    if not item:
        abort(404)
    return render_template("authors/detail.html", author=item)
