from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from annotations import get_model_metadata, get_choices_fields
from utils.generate_from_model import _get_relationship_fields
from model.bookstore.loan import Loan, LoanStatus
from model.core.user_layout_pref import UserLayoutPref
from services.bookstore.loan_service import LoanService
from utils.smart_list import ColumnDef, FilterDef, SmartListConfig, SmartListRenderer
from utils.smart_list.export import export_csv, export_excel, export_pdf

loan_bp = Blueprint("loans", __name__, url_prefix="/loans")

# ── Configuração SmartList (estática — sem queries de banco) ──────────────────
# Filtros @choices NÃO aparecem aqui: são adicionados dinamicamente em list()
# porque dependem de uma query SELECT DISTINCT (precisa de app context + DB).
# O gerador já remove da lista abaixo qualquer Filter cujo campo tenha @choices,
# então não há duplicação entre filtro estático e filtro dinâmico.

SMART_LIST_CONFIG = SmartListConfig(
    list_id="loans",
    endpoint="loans.list",
    columns=[
        ColumnDef("id", "ID", sortable=True, width="60px", align="start"),
        ColumnDef("user_username", "Usuário", sortable=False, width=None, align="start"),
        ColumnDef("book_title", "Livro", sortable=False, width=None, align="start"),
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

# ── Helpers de metadados (executados no import — só leem o mapper, sem DB) ────

def _get_enum_fields():
    """Detecta campos Enum do modelo para gerar <select> no modal."""
    from sqlalchemy import Enum as SAEnum
    from sqlalchemy.orm import ColumnProperty
    from enum import EnumMeta
    import inspect

    result   = []
    metadata = get_model_metadata(Loan)
    form_fields  = metadata.get("ui_form", {}).get("fields", [])
    model_module = inspect.getmodule(Loan)

    for field_name in form_fields:
        options = None
        attr = getattr(Loan, field_name, None)
        if attr is not None and hasattr(attr, "type"):
            col_type = attr.type
            if isinstance(col_type, SAEnum) and getattr(col_type, "enum_class", None):
                enum_class = col_type.enum_class
                options = [(e.value, e.name.replace("_", " ").title()) for e in enum_class]
        if options is None and Loan.__mapper__:
            for prop in Loan.__mapper__.iterate_properties:
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
    for prop in Loan.__mapper__.iterate_properties:
        if isinstance(prop, ColumnProperty):
            col = prop.columns[0]
            if isinstance(col.type, (DateTime, Date)):
                result.append(prop.key)
    return result


def _get_required_fields():
    """Detecta campos marcados com @required."""
    validations = getattr(Loan, "_validations", {})
    return [
        f for f, rules in validations.items()
        if any(r.get("type") == "required" for r in rules)
    ]


# Executados no import — seguros pois só leem o mapper SQLAlchemy (sem query)
ENUM_FIELDS     = _get_enum_fields()
DATE_FIELDS     = _get_date_fields()
REQUIRED_FIELDS = _get_required_fields()
CHOICES_META    = get_choices_fields(Loan)  # [{field, label, order}, ...]


def _build_choices_filters(service: "LoanService") -> list[FilterDef]:
    """
    Constrói FilterDefs com SELECT DISTINCT para campos @choices.
    Recebe o `service` já instanciado pelo chamador (list()) — nunca
    instancia nada aqui, para evitar bugs de ordem/escopo.
    """
    result = []
    for ch in CHOICES_META:
        field = ch["field"]
        label = ch["label"]
        try:
            options = service.distinct_values(field)
        except Exception:
            options = []
        result.append(FilterDef(name=field, label=label, type="select", options=options))
    return result


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

    # 1) Service primeiro — tudo que depende dele vem depois, nunca antes.
    service = LoanService()

    # 2) Filtros @choices (SELECT DISTINCT) — precisa do service e do app context.
    choices_filters = _build_choices_filters(service)
    if choices_filters:
        from copy import copy
        cfg = copy(SMART_LIST_CONFIG)
        cfg.filters = SMART_LIST_CONFIG.filters + choices_filters
    else:
        cfg = SMART_LIST_CONFIG

    # 3) Valores de filtro @choices vindos da query string (ex.: ?genre=Suspense)
    extra_filters = {
        ch["field"]: request.args.get(ch["field"], "").strip() or None
        for ch in CHOICES_META
    }
    extra_filters = {k: v for k, v in extra_filters.items() if v}

    # 4) Busca os dados
    result = service.list(
        page=int(request.args.get("page", 1)),
        per_page=per_page,
        status=status,
        search=request.args.get("search", "").strip() or None,
        sort=request.args.get("sort", cfg.default_sort),
        direction=request.args.get("dir", cfg.default_dir),
        extra_filters=extra_filters,
    )

    if export in ("csv", "excel", "pdf"):
        all_result   = service.list(page=1, per_page=10_000, status=status, extra_filters=extra_filters)
        visible_cols = (user_layout or {}).get("columns") or None
        if export == "csv":
            return export_csv(cfg, all_result.items, visible_cols)
        if export == "excel":
            return export_excel(cfg, all_result.items, visible_cols)
        if export == "pdf":
            return export_pdf(cfg, all_result.items, visible_cols, title="Empréstimoss")

    renderer = SmartListRenderer(cfg)
    sl = renderer.build_context(
        items=result.items,
        total=result.total,
        pages=result.pages,
        user_layout=user_layout,
    )

    metadata = get_model_metadata(Loan)
    form_fields_list    = metadata.get("ui_form", {}).get("fields", [])
    relationship_fields = _get_relationship_fields(Loan)

    return render_template(
        "bookstore/loans/manage.html",
        sl=sl,
        counts=service.count_by_status(),
        current_status=status,
        form_fields_list=form_fields_list,
        relationship_fields=relationship_fields,
        enum_fields=ENUM_FIELDS,
        date_fields=DATE_FIELDS,
        required_fields=REQUIRED_FIELDS,
        class_name="Loan",
        class_name_lower="loan",
        label="Empréstimos",
        plural="loans",
        output_subdir="bookstore",
    )


# ── Detalhe ───────────────────────────────────────────────────────────────────

@loan_bp.route("/<int:item_id>")
@login_required
def detail(item_id: int):
    service = LoanService()
    item = service.get_by_id(item_id)
    if not item:
        abort(404)

    metadata = get_model_metadata(Loan)
    form_fields_list    = metadata.get("ui_form", {}).get("fields", [])
    relationship_fields = _get_relationship_fields(Loan)

    return render_template(
        "bookstore/loans/detail.html",
        loan=item,
        form_fields_list=form_fields_list,
        relationship_fields=relationship_fields,
        enum_fields=ENUM_FIELDS,
        date_fields=DATE_FIELDS,
        required_fields=REQUIRED_FIELDS,
        class_name="Loan",
        class_name_lower="loan",
        label="Empréstimos",
        plural="loans",
        output_subdir="bookstore",
    )


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
