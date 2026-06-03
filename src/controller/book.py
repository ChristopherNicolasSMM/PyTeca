from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from model.book import BookStatus
from model.user_layout_pref import UserLayoutPref
from services.book_service import book_service
from utils.smart_list import ColumnDef, FilterDef, SmartListConfig, SmartListRenderer
from utils.smart_list.export import export_csv, export_excel, export_pdf

book_bp = Blueprint("books", __name__, url_prefix="/books")


# ── Configuração da SmartList de livros ──────────────────────────────────────

def _genre_options():
    """Callable para opções dinâmicas de gênero (carregado a cada request)."""
    return [("", "Todos")] + [(g, g) for g in book_service.get_genres()]


BOOKS_SMART_LIST = SmartListConfig(
    list_id="books",
    endpoint="books.list_books",
    columns=[
        ColumnDef("title",      "Título / Autor",  sortable=True),
        ColumnDef("isbn",       "ISBN",             sortable=False, width="130px"),
        ColumnDef("publisher",  "Editora",          sortable=True,  hidden_default=True),
        ColumnDef("genre",      "Gênero",           sortable=True,  width="120px"),
        ColumnDef("year",       "Ano",              sortable=True,  width="70px",  align="center"),
        ColumnDef("available",  "Estoque",          sortable=True,  width="90px",  align="center"),
        ColumnDef("status",     "Status",           sortable=False, width="100px", align="center"),
        ColumnDef("updated_at", "Atualizado",       sortable=True,  width="130px", hidden_default=True),
    ],
    filters=[
        FilterDef("search", "Buscar",  type="text",   placeholder="Título ou autor…"),
        FilterDef("genre",  "Gênero",  type="select", options=_genre_options),
    ],
    default_sort="title",
    default_dir="asc",
    page_sizes=[10, 20, 50, 100],
    default_page_size=20,
    exportable=True,
    export_filename="livros",
)


# ── Listagem ──────────────────────────────────────────────────────────────────

@book_bp.route("/")
@login_required
def list_books():
    status  = request.args.get("status", BookStatus.ACTIVE)
    export  = request.args.get("export", "")

    user_layout = None
    if current_user.is_authenticated:
        pref = UserLayoutPref.get_for_user(current_user.id, BOOKS_SMART_LIST.list_id)
        if pref:
            user_layout = pref.layout

    per_page = int(request.args.get(
        "per_page",
        (user_layout or {}).get("per_page", BOOKS_SMART_LIST.default_page_size),
    ))

    result = book_service.list_books(
        page=int(request.args.get("page", 1)),
        per_page=per_page,
        status=status,
        search=request.args.get("search", "").strip() or None,
        genre=request.args.get("genre",  "").strip() or None,
        sort=request.args.get("sort", BOOKS_SMART_LIST.default_sort),
        direction=request.args.get("dir", BOOKS_SMART_LIST.default_dir),
    )

    # ── Export ────────────────────────────────────────────────────────────
    if export in ("csv", "excel", "pdf"):
        all_result = book_service.list_books(
            page=1, per_page=10_000,
            status=status,
            search=request.args.get("search", "").strip() or None,
            genre=request.args.get("genre",  "").strip() or None,
            sort=request.args.get("sort", BOOKS_SMART_LIST.default_sort),
            direction=request.args.get("dir", BOOKS_SMART_LIST.default_dir),
        )
        visible_cols = (user_layout or {}).get("columns") or None
        if export == "csv":
            return export_csv(BOOKS_SMART_LIST, all_result.items, visible_cols)
        if export == "excel":
            return export_excel(BOOKS_SMART_LIST, all_result.items, visible_cols)
        if export == "pdf":
            return export_pdf(BOOKS_SMART_LIST, all_result.items, visible_cols, title="Acervo de Livros")

    # ── SmartList context ─────────────────────────────────────────────────
    renderer = SmartListRenderer(BOOKS_SMART_LIST)
    sl = renderer.build_context(
        items=result.items,
        total=result.total,
        pages=result.pages,
        user_layout=user_layout,
    )

    return render_template(
        "books/manage.html",
        sl=sl,
        counts=book_service.count_by_status(),
        current_status=status,
    )


# ── Detalhe ───────────────────────────────────────────────────────────────────

@book_bp.route("/<int:book_id>")
@login_required
def detail(book_id: int):
    print(f"DEBUG: Acessando detalhe do livro {book_id}")
    book = book_service.get_by_id(book_id)
    if not book:
        abort(404)
    return render_template("books/detail.html", book=book)


## ── Novo livro ────────────────────────────────────────────────────────────────
#
#@book_bp.route("/new")
#@login_required
#def new_book():
#    pass
#    result = book_service.create_draft()
#    draft  = result.data
#    return render_template(
#        "books/form.html",
#        book=draft,
#        mode="create",
#        autosave_url=url_for("books_api.autosave_draft", book_id=draft.id),
#        publish_url=url_for("books_api.publish_draft",   book_id=draft.id),
#    )
#
#
## ── Edição ────────────────────────────────────────────────────────────────────
#
#@book_bp.route("/<int:book_id>/edit")
#@login_required
#def edit_book(book_id: int):
#    pass
#    book = book_service.get_by_id(book_id)
#    if not book:
#        abort(404)
#    if book.is_trashed:
#        flash("Este livro está na lixeira. Restaure-o para editar.", "warning")
#        return redirect(url_for("books.list_books", status="trash"))
#    return render_template(
#        "books/form.html",
#        book=book,
#        mode="edit",
#        autosave_url=url_for("books_api.update_book", book_id=book.id),
#        publish_url=url_for("books_api.update_book",  book_id=book.id),
#    )


# ── Ações POST ────────────────────────────────────────────────────────────────

@book_bp.route("/<int:book_id>/trash", methods=["POST"])
@login_required
def trash_book(book_id: int):
    r = book_service.trash(book_id)
    flash("Livro movido para a lixeira." if r.success else r.error,
          "success" if r.success else "danger")
    return redirect(request.referrer or url_for("books.list_books"))


@book_bp.route("/<int:book_id>/restore", methods=["POST"])
@login_required
def restore_book(book_id: int):
    r = book_service.restore(book_id)
    flash("Livro restaurado com sucesso." if r.success else r.error,
          "success" if r.success else "danger")
    return redirect(request.referrer or url_for("books.list_books", status="trash"))


@book_bp.route("/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id: int):
    if not current_user.is_admin:
        abort(403)
    r = book_service.delete_permanent(book_id)
    flash("Livro excluído permanentemente." if r.success else r.error,
          "success" if r.success else "danger")
    return redirect(url_for("books.list_books", status="trash"))


@book_bp.route("/<int:book_id>/discard", methods=["POST"])
@login_required
def discard_draft(book_id: int):
    r = book_service.discard_draft(book_id)
    flash("Rascunho descartado." if r.success else r.error,
          "info" if r.success else "danger")
    return redirect(url_for("books.list_books"))
