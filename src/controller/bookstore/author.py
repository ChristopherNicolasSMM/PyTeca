from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from annotations import get_model_metadata, get_choices_fields
from utils.generate_from_model import _get_relationship_fields
from model.bookstore.author import Author, AuthorStatus
from model.core.user_layout_pref import UserLayoutPref
from services.bookstore.author_service import AuthorService
from utils.smart_list import ColumnDef, FilterDef, SmartListConfig, SmartListRenderer
from utils.smart_list.export import export_csv, export_excel, export_pdf

author_bp = Blueprint("authors", __name__, url_prefix="/authors")

# ── Configuração SmartList (estática — sem queries de banco) ──────────────────

SMART_LIST_CONFIG = SmartListConfig(
    list_id="authors",
    endpoint="authors.list",
    columns=[
        ColumnDef("id", "ID", sortable=True, width="60px", align="start"),
        ColumnDef("name", "Nome", sortable=True, width=None, align="start"),
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

# ── Helpers de metadados (executados no import — só leem o mapper, sem DB) ────

def _get_enum_fields():
    """Detecta campos Enum do modelo para gerar <select> no modal."""
    from sqlalchemy import Enum as SAEnum
    from sqlalchemy.orm import ColumnProperty
    from enum import EnumMeta
    import inspect

    result   = []
    metadata = get_model_metadata(Author)
    form_fields  = metadata.get("ui_form", {}).get("fields", [])
    model_module = inspect.getmodule(Author)

    for field_name in form_fields:
        options = None
        attr = getattr(Author, field_name, None)
        if attr is not None and hasattr(attr, "type"):
            col_type = attr.type
            if isinstance(col_type, SAEnum) and getattr(col_type, "enum_class", None):
                enum_class = col_type.enum_class
                options = [(e.value, e.name.replace("_", " ").title()) for e in enum_class]
        if options is None and Author.__mapper__:
            for prop in Author.__mapper__.iterate_properties:
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
    for prop in Author.__mapper__.iterate_properties:
        if isinstance(prop, ColumnProperty):
            col = prop.columns[0]
            if isinstance(col.type, (DateTime, Date)):
                result.append(prop.key)
    return result


def _get_required_fields():
    """Detecta campos marcados com @required."""
    validations = getattr(Author, "_validations", {})
    return [
        f for f, rules in validations.items()
        if any(r.get("type") == "required" for r in rules)
    ]


# Executados no import — seguros pois só leem o mapper SQLAlchemy (sem query)
ENUM_FIELDS     = _get_enum_fields()
DATE_FIELDS     = _get_date_fields()
REQUIRED_FIELDS = _get_required_fields()
_CHOICES_META   = get_choices_fields(Author)  # lista de {field, label, order}


def _get_choices_filters(service: AuthorService) -> list[FilterDef]:
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

@author_bp.route("/")
@login_required
def list():
    status = request.args.get("status", AuthorStatus.ACTIVE.value)
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
            return export_pdf(SMART_LIST_CONFIG, all_result.items, visible_cols, title="Autoress")

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

    metadata = get_model_metadata(Author)
    form_fields_list    = metadata.get("ui_form", {}).get("fields", [])
    relationship_fields = _get_relationship_fields(Author)

    return render_template(
        "bookstore/authors/manage.html",
        sl=sl,
        counts=service.count_by_status(),
        current_status=status,
        form_fields_list=form_fields_list,
        relationship_fields=relationship_fields,
        enum_fields=ENUM_FIELDS,
        date_fields=DATE_FIELDS,
        required_fields=REQUIRED_FIELDS,
        class_name="Author",
        class_name_lower="author",
        label="Autores",
        plural="authors",
        output_subdir="bookstore",
    )


# ── Detalhe ───────────────────────────────────────────────────────────────────

@author_bp.route("/<int:item_id>")
@login_required
def detail(item_id: int):
    service = AuthorService()
    item = service.get_by_id(item_id)
    if not item:
        abort(404)

    metadata = get_model_metadata(Author)
    form_fields_list    = metadata.get("ui_form", {}).get("fields", [])
    relationship_fields = _get_relationship_fields(Author)

    return render_template(
        "bookstore/authors/detail.html",
        author=item,
        form_fields_list=form_fields_list,
        relationship_fields=relationship_fields,
        enum_fields=ENUM_FIELDS,
        date_fields=DATE_FIELDS,
        required_fields=REQUIRED_FIELDS,
        class_name="Author",
        class_name_lower="author",
        label="Autores",
        plural="authors",
        output_subdir="bookstore",
    )


# ── Ações POST ────────────────────────────────────────────────────────────────

@author_bp.route("/<int:author_id>/trash", methods=["POST"])
@login_required
def trash(author_id: int):
    service = AuthorService()
    r = service.trash(author_id)
    flash("Movido para a lixeira." if r.success else r.error,
          "success" if r.success else "danger")
    return redirect(request.referrer or url_for("authors.list"))


@author_bp.route("/<int:author_id>/restore", methods=["POST"])
@login_required
def restore(author_id: int):
    service = AuthorService()
    r = service.restore(author_id)
    flash("Registro restaurado." if r.success else r.error,
          "success" if r.success else "danger")
    return redirect(request.referrer or url_for("authors.list", status="trash"))


@author_bp.route("/<int:author_id>/delete", methods=["POST"])
@login_required
def delete_permanent(author_id: int):
    if not current_user.is_admin:
        abort(403)
    service = AuthorService()
    r = service.delete_permanent(author_id)
    flash("Excluído permanentemente." if r.success else r.error,
          "success" if r.success else "danger")
    return redirect(url_for("authors.list", status="trash"))


@author_bp.route("/<int:author_id>/discard", methods=["POST"])
@login_required
def discard_draft(author_id: int):
    service = AuthorService()
    r = service.discard_draft(author_id)
    flash("Rascunho descartado." if r.success else r.error,
          "info" if r.success else "danger")
    return redirect(url_for("authors.list"))
