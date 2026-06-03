from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal


FilterType = Literal["text", "select", "date_range", "number_range", "boolean"]
ColumnAlign = Literal["start", "center", "end"]


@dataclass
class FilterDef:
    """Define um filtro disponível na SmartList."""

    name: str
    """Nome do parâmetro de query string (ex: 'search', 'genre')."""

    label: str
    """Label exibido na UI."""

    type: FilterType = "text"
    """Tipo de controle de filtro."""

    placeholder: str = ""
    """Placeholder para campos de texto."""

    options: list[tuple[str, str]] | Callable[[], list[tuple[str, str]]] | None = None
    """Para type='select': lista de (value, label) ou callable que retorna a lista."""

    default: Any = None
    """Valor padrão quando não informado."""

    width: str = "auto"
    """Largura CSS do controle (ex: '180px', 'auto')."""


@dataclass
class ColumnDef:
    """Define uma coluna da tabela SmartList."""

    key: str
    """Chave usada no sort e como identificador único."""

    label: str
    """Cabeçalho da coluna."""

    sortable: bool = True
    """Se a coluna permite ordenação."""

    align: ColumnAlign = "start"
    """Alinhamento do conteúdo."""

    width: str | None = None
    """Largura fixa (ex: '120px'). None = automático."""

    render: str | None = None
    """
    Nome do macro Jinja2 para renderizar o valor da célula.
    Se None, usa renderização padrão ({{ row[key] }}).
    """

    hidden_default: bool = False
    """Se True, a coluna começa oculta (usuário pode reativar)."""


@dataclass
class SmartListConfig:
    """
    Configuração completa de uma SmartList.

    Exemplo de uso em um controller:

        from utils.smart_list.config import SmartListConfig, ColumnDef, FilterDef

        BOOKS_LIST = SmartListConfig(
            list_id="books",
            endpoint="books.list_books",
            columns=[
                ColumnDef("title",  "Título"),
                ColumnDef("author", "Autor"),
                ColumnDef("isbn",   "ISBN",   sortable=False),
                ColumnDef("status", "Status", align="center", width="100px"),
            ],
            filters=[
                FilterDef("search", "Buscar",  placeholder="Título ou autor…"),
                FilterDef("genre",  "Gênero",  type="select"),
                FilterDef("status", "Status",  type="select", options=[
                    ("active", "Publicados"),
                    ("draft",  "Rascunhos"),
                    ("trash",  "Lixeira"),
                ]),
            ],
            default_sort="title",
            default_dir="asc",
            page_sizes=[10, 20, 50, 100],
            default_page_size=20,
            exportable=True,
            export_filename="livros",
        )
    """

    list_id: str
    """Identificador único desta lista (usado para salvar preferências)."""

    endpoint: str
    """Endpoint Flask para links de sort/paginação (ex: 'books.list_books')."""

    columns: list[ColumnDef] = field(default_factory=list)
    """Colunas visíveis, na ordem padrão."""

    filters: list[FilterDef] = field(default_factory=list)
    """Filtros disponíveis."""

    default_sort: str = ""
    """Chave da coluna para ordenação padrão."""

    default_dir: Literal["asc", "desc"] = "asc"
    """Direção padrão."""

    page_sizes: list[int] = field(default_factory=lambda: [10, 20, 50, 100])
    """Opções de tamanho de página."""

    default_page_size: int = 20
    """Tamanho de página padrão."""

    exportable: bool = True
    """Se True, exibe botões de export."""

    export_filename: str = "export"
    """Nome base do arquivo exportado (sem extensão)."""

    show_count: bool = True
    """Se True, exibe badge com total de registros."""

    allow_layout_save: bool = True
    """Se True, usuário pode salvar/restaurar layout de colunas."""
