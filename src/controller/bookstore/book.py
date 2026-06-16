from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from annotations import get_model_metadata, get_choices_fields
from utils.generate_from_model import _get_relationship_fields
from model.bookstore.book import Book, BookStatus
from model.core.user_layout_pref import UserLayoutPref
from services.bookstore.book_service import BookService
from utils.smart_list import ColumnDef, FilterDef, SmartListConfig, SmartListRenderer
from utils.smart_list.export import export_csv, export_excel, export_pdf

book_bp = Blueprint("books", __name__, url_prefix="/books")

# ── Configuração SmartList (estática — sem queries de banco) ──────────────────

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

# ── Helpers de metadados (executados no import — só leem o mapper, sem DB) ────

def _get_enum_fields():
    """Detecta campos Enum do modelo para gerar <select> no modal."""
    from sqlalchemy import Enum as SAEnum
    from sqlalchemy.orm import ColumnProperty
    from enum import EnumMeta
    import inspect

    result   = []
    metadata = get_model_metadata(Book)
    form_fields  = metadata.get("ui_form", {}).get("fields", [])
    model_module = inspect.getmodule(Book)

    for field_name in form_fields:
        options = None
        attr = getattr(Book, field_name, None)
        if attr is not None and hasattr(attr, "type"):
            col_type = attr.type
            if isinstance(col_type, SAEnum) and getattr(col_type, "enum_class", None):
                enum_class = col_type.enum_class
                options = [(e.value, e.name.replace("_", " ").title()) for e in enum_class]
        if options is None and Book.__mapper__:
            for prop in Book.__mapper__.iterate_properties:
                if isinstance(prop, ColumnProperty) and prop.key == field_name:
                    for obj_name, obj in vars(model_module).items():
                        if isinstance(obj, EnumMeta) and field_name.replace("_", "").lower() in obj_name.lower():
                            options = [(e.value, e.name.replace("_", " ").title()) for e in obj]
                            break
        if options:
            result.append({"name": field_name, "options": options})
    return result


def _get_date_fields():
    """Detecta campos DateTime/Date do modelo."""
    from sqlalchemy import DateTime, Date
    from sqlalchemy.orm import ColumnProperty
    result = []
    for prop in Book.__mapper__.iterate_properties:
        if isinstance(prop, ColumnProperty):
            col = prop.columns[0]
            if isinstance(col.type, (DateTime, Date)):
                result.append(prop.key)
    return result


def _get_required_fields():
    """Detecta campos marcados com @required."""
    validations = getattr(Book, "_validations", {})
    return [
        f for f, rules in validations.items()
        if any(r.get("type") == "required" for r in rules)
    ]


# Executados no import — seguros pois só leem o mapper SQLAlchemy (sem query)
ENUM_FIELDS     = _get_enum_fields()
DATE_FIELDS     = _get_date_fields()
REQUIRED_FIELDS = _get_required_fields()
_CHOICES_META   = get_choices_fields(Book)  # lista de {field, label, order}


def _get_choices_filters(service: BookService) -> list[FilterDef]:
    """
    Constrói FilterDefs com SELECT DISTINCT para campos @choices.
    Chamado DENTRO de list() — já dentro do app context com DB disponível.
    """
    filters = []
    for ch in _CHOICES_META:
        field = ch["field"]
        label = ch["label"]
        try:
            options = service.distinct_values(field)
        except Exception:
            options = []
        filters.append(FilterDef(name=field, label=label, type="select", options=options))
    return filters


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
    result  = service.list(
        page=int(request.args.get("page", 1)),
        per_page=per_page,
        status=status,
        search=request.args.get("search", "").strip() or None,
        sort=request.args.get("sort", SMART_LIST_CONFIG.default_sort),
        direction=request.args.get("dir", SMART_LIST_CONFIG.default_dir),
    )

    if export in ("csv", "excel", "pdf"):
        all_result  = service.list(page=1, per_page=10_000, status=status)
        visible_cols = (user_layout or {}).get("columns") or None
        if export == "csv":
            return export_csv(SMART_LIST_CONFIG, all_result.items, visible_cols)
        if export == "excel":
            return export_excel(SMART_LIST_CONFIG, all_result.items, visible_cols)
        if export == "pdf":
            return export_pdf(SMART_LIST_CONFIG, all_result.items, visible_cols, title="Livross")

    # ── Filtros @choices (SELECT DISTINCT) — lazy, dentro do app context ──────
    choices_filters = _get_choices_filters(service)

    # Injeta filtros @choices no config para o renderer os incluir
    if choices_filters:
        from copy import copy
        cfg_with_choices = copy(SMART_LIST_CONFIG)
        cfg_with_choices.filters = SMART_LIST_CONFIG.filters + choices_filters
    else:
        cfg_with_choices = SMART_LIST_CONFIG

    renderer = SmartListRenderer(cfg_with_choices)
    sl = renderer.build_context(
        items=result.items,
        total=result.total,
        pages=result.pages,
        user_layout=user_layout,
    )

    metadata = get_model_metadata(Book)
    form_fields_list    = metadata.get("ui_form", {}).get("fields", [])
    relationship_fields = _get_relationship_fields(Book)

    return render_template(
        "bookstore/books/manage.html",
        sl=sl,
        counts=service.count_by_status(),
        current_status=status,
        form_fields_list=form_fields_list,
        relationship_fields=relationship_fields,
        enum_fields=ENUM_FIELDS,
        date_fields=DATE_FIELDS,
        required_fields=REQUIRED_FIELDS,
        class_name="Book",
        class_name_lower="book",
        label="Livros",
        plural="books",
        output_subdir="bookstore",
    )


# ── Detalhe ───────────────────────────────────────────────────────────────────

@book_bp.route("/<int:item_id>")
@login_required
def detail(item_id: int):
    service = BookService()
    item = service.get_by_id(item_id)
    if not item:
        abort(404)

    metadata = get_model_metadata(Book)
    form_fields_list    = metadata.get("ui_form", {}).get("fields", [])
    relationship_fields = _get_relationship_fields(Book)

    return render_template(
        "bookstore/books/detail.html",
        book=item,
        form_fields_list=form_fields_list,
        relationship_fields=relationship_fields,
        enum_fields=ENUM_FIELDS,
        date_fields=DATE_FIELDS,
        required_fields=REQUIRED_FIELDS,
        class_name="Book",
        class_name_lower="book",
        label="Livros",
        plural="books",
        output_subdir="bookstore",
    )


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
