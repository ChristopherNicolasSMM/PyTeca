# annotations/__init__.py
from typing import List, Optional, Callable, Any, Dict
import inspect

# ---- Decorators para entidade ----
def label(value: str):
    def decorator(cls):
        cls._entity_label = value
        return cls
    return decorator

def plural(value: str):
    def decorator(cls):
        cls._entity_plural = value
        return cls
    return decorator

# ---- Decorators para UI (SmartList) ----
class Column:
    def __init__(self, name: str, label: Optional[str] = None, width: Optional[str] = None,
                 sortable: bool = False, filterable: bool = False, align: str = "start"):
        self.name = name
        self.label = label or name.replace('_', ' ').title()
        self.width = width
        self.sortable = sortable
        self.filterable = filterable
        self.align = align

class Filter:
    def __init__(self, name: str, type: str = "text", placeholder: Optional[str] = None,
                 options: Optional[List[tuple]] = None, options_callable: Optional[Callable] = None):
        self.name = name
        self.type = type
        self.placeholder = placeholder
        self.options = options
        self.options_callable = options_callable

def listview(columns: List[Column], default_sort: Optional[str] = None,
             filters: Optional[List[Filter]] = None):
    def decorator(cls):
        cls._ui_listview = {
            "columns": [c.__dict__ for c in columns],
            "default_sort": default_sort,
            "filters": [f.__dict__ for f in (filters or [])]
        }
        return cls
    return decorator

# ---- Decorators para formulário ----
class Group:
    def __init__(self, name: str, label: str, fields: List[str], collapsible: bool = False):
        self.name = name
        self.label = label
        self.fields = fields
        self.collapsible = collapsible

def form(fields: List[str], groups: Optional[List[Group]] = None):
    def decorator(cls):
        cls._ui_form = {
            "fields": fields,
            "groups": [g.__dict__ for g in (groups or [])]
        }
        return cls
    return decorator

# ---- Decorators de validação ----
def required(field: str, message: Optional[str] = None):
    def decorator(cls):
        cls._validations = getattr(cls, '_validations', {})
        cls._validations.setdefault(field, []).append({
            "type": "required",
            "message": message or f"{field} é obrigatório"
        })
        return cls
    return decorator

def max_length(field: str, max: int, message: Optional[str] = None):
    def decorator(cls):
        cls._validations = getattr(cls, '_validations', {})
        cls._validations.setdefault(field, []).append({
            "type": "max_length",
            "max": max,
            "message": message or f"{field} deve ter no máximo {max} caracteres"
        })
        return cls
    return decorator

def min_length(field: str, min: int, message: Optional[str] = None):
    def decorator(cls):
        cls._validations = getattr(cls, '_validations', {})
        cls._validations.setdefault(field, []).append({
            "type": "min_length",
            "min": min,
            "message": message or f"{field} deve ter no mínimo {min} caracteres"
        })
        return cls
    return decorator

def min_value(field: str, min: int, message: Optional[str] = None):
    def decorator(cls):
        cls._validations = getattr(cls, '_validations', {})
        cls._validations.setdefault(field, []).append({
            "type": "min_value",
            "min": min,
            "message": message or f"{field} deve ser no mínimo {min}"
        })
        return cls
    return decorator

def display_field(value: str):
    """Define qual campo deve ser usado como display name para este model (ex: 'username', 'title')."""
    def decorator(cls):
        cls._display_field = value
        return cls
    return decorator

# ---- Extração de metadados ----
def get_model_metadata(cls) -> Dict[str, Any]:
    """Extrai todos os metadados anotados de uma classe."""
    return {
        "name": cls.__name__,
        "label": getattr(cls, '_entity_label', cls.__name__),
        "plural": getattr(cls, '_entity_plural', cls.__name__.lower() + 's'),
        "ui_listview": getattr(cls, '_ui_listview', None),
        "ui_form": getattr(cls, '_ui_form', None),
        "validations": getattr(cls, '_validations', {}),
    }    
    
# ---- Ajustes para o menu ----
def menu_icon(value: str):
    def decorator(cls):
        cls._menu_icon = value
        return cls
    return decorator

def menu_parent(value: str):
    def decorator(cls):
        cls._menu_parent = value
        return cls
    return decorator    

# ---- @choices: SELECT DISTINCT automático para filtros ----
def choices(field: str, label: str | None = None, order: str = "asc"):
    """
    Marca um campo do modelo para ter opções dinâmicas via SELECT DISTINCT.

    Uso no model:
        @choices("genre", label="Gênero")
        @choices("language", label="Idioma")
        class Book(db.Model):
            genre: Mapped[str] = mapped_column(String(60))

    O gerador e o controller usam _choices_fields para construir
    FilterDef com options=lambda: BookService.distinct_values("genre")

    Parâmetros:
        field: nome da coluna no modelo
        label: label exibido no filtro (padrão: field.title())
        order: "asc" ou "desc" para ordenar as opções
    """
    def decorator(cls):
        if not hasattr(cls, '_choices_fields'):
            cls._choices_fields = []
        cls._choices_fields.append({
            "field": field,
            "label": label or field.replace("_", " ").title(),
            "order": order,
        })
        return cls
    return decorator


def get_choices_fields(cls) -> list[dict]:
    """Retorna a lista de campos com @choices definidos."""
    return getattr(cls, '_choices_fields', [])


# ---- @permission: Camada 2 (granularidade de negócio) ----
def permission(action: str, role_required: str | None = None, description: str | None = None):
    """
    Declara que uma ação de negócio deste model exige uma permissão específica.

    Diferente da Camada 1 (rota, automática — toda rota gerada já recebe
    @permission_required("<plural>.<acao>")), esta anotação serve para
    ações que não mapeiam 1:1 para uma rota, ou quando você quer atribuir
    uma permissão a um papel específico já no momento da geração.

    Uso no model:
        @permission("trash", role_required="librarian",
                     description="Mover livro para a lixeira")
        @permission("delete_permanent", role_required="admin")
        class Book(db.Model):
            ...

    Fluxo (código lidera, banco segue):
        1. Você escreve @permission(...) no model.
        2. Ao rodar `generate`, o gerador sincroniza automaticamente uma
           linha em `permissions` (cria se não existir, nunca duplica).
        3. Se role_required for informado e o Role já existir, a
           associação Role<->Permission também é garantida.
        4. A UI de Admin Roles NUNCA cria Permission do zero — ela só
           lê o que o código gerou e permite associar a outros Roles
           ou atribuir Roles a usuários.

    O nome da permissão sincronizada segue o padrão "<plural>.<action>",
    ex: "books.trash", "books.delete_permanent" — mesmo padrão da Camada 1,
    para nunca haver dois formatos de nome de permissão coexistindo.
    """
    def decorator(cls):
        if not hasattr(cls, '_permissions'):
            cls._permissions = []
        cls._permissions.append({
            "action": action,
            "role_required": role_required,
            "description": description or f"Permite '{action}' em {cls.__name__}",
        })
        return cls
    return decorator


def get_permissions_meta(cls) -> list[dict]:
    """Retorna a lista de permissões de negócio (@permission) declaradas no model."""
    return getattr(cls, '_permissions', [])
