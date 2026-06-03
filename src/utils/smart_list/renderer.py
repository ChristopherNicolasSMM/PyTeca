from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import request, url_for
from flask_login import current_user

from utils.smart_list.config import ColumnDef, FilterDef, SmartListConfig


@dataclass
class ResolvedFilter:
    """Filtro com valor atual resolvido da query string."""

    defn: FilterDef
    value: Any
    options: list[tuple[str, str]]  # sempre lista resolvida (mesmo para callable)


@dataclass
class ResolvedColumn:
    """Coluna com estado de visibilidade e sort aplicados."""

    defn: ColumnDef
    visible: bool
    sort_url: str | None  # None se não sortável
    is_sorted: bool
    sort_dir: str  # 'asc' | 'desc' | ''


@dataclass
class SmartListContext:
    """
    Contexto completo passado ao template.
    Tudo que o macro smart_list.html precisa.
    """

    config: SmartListConfig

    # Estado atual
    columns: list[ResolvedColumn]
    filters: list[ResolvedFilter]
    current_sort: str
    current_dir: str
    current_page: int
    current_per_page: int

    # Resultado (preenchido pelo controller)
    total: int
    pages: int
    items: list[Any]

    # URLs pré-computadas
    export_url_excel: str
    export_url_csv: str
    export_url_pdf: str

    # Paginação
    page_urls: list[tuple[int, str]]  # [(page_num, url), ...]
    prev_url: str | None
    next_url: str | None

    # Layout
    layout_save_url: str
    layout_reset_url: str
    user_has_custom_layout: bool


class SmartListRenderer:
    """
    Prepara o SmartListContext a partir de:
    - SmartListConfig (definição estática)
    - request.args (estado atual da query string)
    - layout salvo do usuário (do banco)
    - resultado de paginação do serviço
    """

    def __init__(self, config: SmartListConfig):
        self.config = config

    def build_context(
        self,
        *,
        items: list[Any],
        total: int,
        pages: int,
        user_layout: dict | None = None,
    ) -> SmartListContext:
        """
        Constrói o contexto para o template.

        Args:
            items:       lista de registros da página atual
            total:       total de registros (para badge)
            pages:       total de páginas
            user_layout: dict com {'columns': [...], 'per_page': N} salvo do banco
                         ou None para usar padrão
        """
        cfg = self.config
        args = request.args

        # ── Estado atual ──────────────────────────────────────────────────────
        current_sort = args.get("sort", cfg.default_sort)
        current_dir = args.get("dir", cfg.default_dir)
        current_page = max(1, int(args.get("page", 1)))
        current_per_page = int(args.get("per_page", cfg.default_page_size))
        if current_per_page not in cfg.page_sizes:
            current_per_page = cfg.default_page_size

        # ── Colunas (aplica layout do usuário se existir) ─────────────────────
        column_order = (user_layout or {}).get("columns", [c.key for c in cfg.columns])
        hidden_keys = set((user_layout or {}).get("hidden", []))

        # Reordena e filtra colunas segundo layout salvo
        col_map = {c.key: c for c in cfg.columns}
        ordered_keys = [k for k in column_order if k in col_map]
        # Garante colunas novas (não no layout salvo) apareçam no final
        for c in cfg.columns:
            if c.key not in ordered_keys:
                ordered_keys.append(c.key)

        resolved_columns: list[ResolvedColumn] = []
        for key in ordered_keys:
            col = col_map[key]
            visible = key not in hidden_keys and not (
                col.hidden_default and user_layout is None
            )

            if col.sortable:
                next_dir = "desc" if (current_sort == key and current_dir == "asc") else "asc"
                sort_url = self._build_url(sort=key, dir=next_dir, page=1)
            else:
                sort_url = None

            resolved_columns.append(ResolvedColumn(
                defn=col,
                visible=visible,
                sort_url=sort_url,
                is_sorted=current_sort == key,
                sort_dir=current_dir if current_sort == key else "",
            ))

        # ── Filtros (resolve opções e valores) ────────────────────────────────
        resolved_filters: list[ResolvedFilter] = []
        for flt in cfg.filters:
            value = args.get(flt.name, flt.default or "")
            if callable(flt.options):
                options = flt.options()
            elif flt.options:
                options = list(flt.options)
            else:
                options = []
            resolved_filters.append(ResolvedFilter(defn=flt, value=value, options=options))

        # ── URLs de export ────────────────────────────────────────────────────
        base_params = self._current_params(exclude={"page", "per_page", "export"})
        export_excel = self._build_url(**base_params, export="excel")
        export_csv = self._build_url(**base_params, export="csv")
        export_pdf = self._build_url(**base_params, export="pdf")

        # ── Paginação ─────────────────────────────────────────────────────────
        page_urls = [
            (p, self._build_url(page=p))
            for p in range(1, pages + 1)
        ]
        prev_url = self._build_url(page=current_page - 1) if current_page > 1 else None
        next_url = self._build_url(page=current_page + 1) if current_page < pages else None

        # ── Layout URLs ───────────────────────────────────────────────────────
        layout_save_url = url_for("smart_list_api.save_layout")
        layout_reset_url = url_for("smart_list_api.reset_layout", list_id=cfg.list_id)

        return SmartListContext(
            config=cfg,
            columns=resolved_columns,
            filters=resolved_filters,
            current_sort=current_sort,
            current_dir=current_dir,
            current_page=current_page,
            current_per_page=current_per_page,
            total=total,
            pages=pages,
            items=items,
            export_url_excel=export_excel,
            export_url_csv=export_csv,
            export_url_pdf=export_pdf,
            page_urls=page_urls,
            prev_url=prev_url,
            next_url=next_url,
            layout_save_url=layout_save_url,
            layout_reset_url=layout_reset_url,
            user_has_custom_layout=user_layout is not None,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _current_params(self, exclude: set[str] | None = None) -> dict:
        """Retorna todos os parâmetros atuais da query string como dict."""
        exclude = exclude or set()
        return {k: v for k, v in request.args.items() if k not in exclude}

    def _build_url(self, **overrides) -> str:
        """Constrói URL do endpoint preservando parâmetros atuais e aplicando overrides."""
        params = self._current_params()
        params.update({k: v for k, v in overrides.items() if v is not None})
        # Remove parâmetros vazios
        params = {k: v for k, v in params.items() if v != ""}
        try:
            return url_for(self.config.endpoint, **params)
        except Exception:
            return "#"
