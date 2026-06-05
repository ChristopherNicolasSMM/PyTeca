from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from model.book import Book, BookStatus
from model.user_layout_pref import UserLayoutPref
from services.book.book_service import BookService
from utils.smart_list import ColumnDef, FilterDef, SmartListConfig, SmartListRenderer
from utils.smart_list.export import export_csv, export_excel, export_pdf

book_bp = Blueprint("books", __name__, url_prefix="/books")

# ── Configuração SmartList ────────────────────────────────────────────────────

SMART_LIST_CONFIG = SmartListConfig(
    list_id="books",
    endpoint="books.list",
    columns=[
        ColumnDef("id", "ID", sortable=True, width="60px", align="start"),
        ColumnDef("title", "Título", sortable=True, width=None, align="start"),
        ColumnDef("author", "Autor", sortable=True, width=None, align="start"),
        ColumnDef("year", "Ano", sortable=False, width="80px", align="center"),
        ColumnDef("available", "Disponível", sortable=False, width="90px", align="center"),
        ColumnDef("status", "Status", sortable=False, width="100px", align="center")
    ],
    filters=[
        FilterDef("search", "search", type="text", placeholder="Título ou autor..."),
        FilterDef("genre", "genre", type="text", placeholder="Gênero")
    ],
    default_sort="title",
    default_dir="asc",
    page_sizes=[10, 20, 50, 100],
    default_page_size=20,
    exportable=True,
    export_filename="books",
)


# ── Listagem ──────────────────────────────────────────────────────────────────

@book_bp.route("/")
@login_required
def list():
    status = request.args.get("status", BookStatus.ACTIVE.value)
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

    service = BookService()
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
            return export_pdf(SMART_LIST_CONFIG, all_result.items, visible_cols, title="Livross")

    renderer = SmartListRenderer(SMART_LIST_CONFIG)
    sl = renderer.build_context(
        items=result.items,
        total=result.total,
        pages=result.pages,
        user_layout=user_layout,
    )

    return render_template(
        "books/manage.html",
        sl=sl,
        counts=service.count_by_status(),
        current_status=status,
    )


# ── Detalhe ───────────────────────────────────────────────────────────────────

@book_bp.route("/<int:item_id>")
@login_required
def detail(item_id: int):
    service = BookService()
    item = service.get_by_id(item_id)
    if not item:
        abort(404)
    return render_template("books/detail.html", book=item)


# ── Ações POST ────────────────────────────────────────────────────────────────

@book_bp.route("/<int:book_id>/trash", methods=["POST"])
@login_required
def trash(book_id: int):
    service = BookService()
    r = service.trash(book_id)
    flash("Movido para a lixeira." if r.success else r.error,
          "success" if r.success else "danger")
    return redirect(request.referrer or url_for("books.list"))


@book_bp.route("/<int:book_id>/restore", methods=["POST"])
@login_required
def restore(book_id: int):
    service = BookService()
    r = service.restore(book_id)
    flash("Registro restaurado." if r.success else r.error,
          "success" if r.success else "danger")
    return redirect(request.referrer or url_for("books.list", status="trash"))


@book_bp.route("/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_permanent(book_id: int):
    if not current_user.is_admin:
        abort(403)
    service = BookService()
    r = service.delete_permanent(book_id)
    flash("Excluído permanentemente." if r.success else r.error,
          "success" if r.success else "danger")
    return redirect(url_for("books.list", status="trash"))


@book_bp.route("/<int:book_id>/discard", methods=["POST"])
@login_required
def discard_draft(book_id: int):
    service = BookService()
    r = service.discard_draft(book_id)
    flash("Rascunho descartado." if r.success else r.error,
          "info" if r.success else "danger")
    return redirect(url_for("books.list"))
