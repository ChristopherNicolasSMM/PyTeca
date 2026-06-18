# utils/generate_from_model.py
"""
Gerador automático de CRUD a partir de modelos SQLAlchemy anotados.

Uso via Flask CLI:
    flask generate --model model/author.py
    flask generate --model model/bookstore/loan.py   # subpasta
    flask generate --model model/bookstore           # pasta inteira (futuro)
    flask generate                                   # usa config.yaml

Os templates ficam em:
    utils/generate_model/templates/<tema>/
O tema padrão é 'standard'.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from annotations import get_model_metadata
from utils.generate_model.template_loader import get_loader


def _find_project_root(start_path: Path) -> Optional[Path]:
    """
    Encontra a raiz do projeto procurando por um diretório 'src' ou
    arquivos de marcadores como 'main.py', 'app.py' ou '.flaskenv'.
    """
    current = start_path.resolve()
    
    # Primeiro, tenta encontrar o diretório 'src'
    while current.parent != current:
        # Verifica se o diretório atual ou um dos pais contém 'src'
        test_src = current / 'src'
        if test_src.is_dir() and (test_src / 'main.py').exists():
            return current
        
        # Também verifica se há um arquivo marcador na raiz
        for marker in ['main.py', 'app.py', '.flaskenv', 'requirements.txt']:
            if (current / marker).exists():
                # Verifica se há um diretório 'src' neste nível
                if (current / 'src').is_dir():
                    return current
        
        current = current.parent
    
    # Fallback: procura de baixo para cima por um diretório que contenha 'src/main.py'
    current = start_path
    while current.parent != current:
        if (current / 'main.py').exists() or (current / 'src' / 'main.py').exists():
            return current
        current = current.parent
    
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CARREGAMENTO DE CONFIGURAÇÃO YAML
# ══════════════════════════════════════════════════════════════════════════════

def load_config(config_path: str = "utils/generate_model/config.yaml") -> Dict:
    """Carrega o arquivo de configuração YAML."""
    import yaml
    config_file = Path(__file__).parent / "generate_model" / "config.yaml"
    if not config_file.exists():
        print(f"Arquivo de configuração não encontrado: {config_file}")
        return {}
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ══════════════════════════════════════════════════════════════════════════════
# CARREGAMENTO DE CLASSES DO ARQUIVO MODEL
# ══════════════════════════════════════════════════════════════════════════════

def load_classes_from_file(
    file_path: str,
    class_name: Optional[str] = None,
) -> List[tuple]:
    """
    Carrega classes de um arquivo Python que são subclasses de db.Model.
    Evita recarregar módulos já importados.
    """
    import sys
    import importlib
    import inspect

    full_path = Path(file_path).resolve()
    
    if not full_path.exists():
        print(f"  ✗ Arquivo não encontrado: {full_path}")
        return []

    # Encontra a raiz do projeto
    project_root = _find_project_root(full_path)
    if not project_root:
        print(f"  ✗ Não foi possível encontrar a raiz do projeto para: {full_path}")
        return []

    # Adiciona a raiz ao sys.path se necessário
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Calcula o nome do módulo
    try:
        rel_path = full_path.relative_to(project_root)
        module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')
    except ValueError:
        if 'src' in str(full_path):
            src_idx = str(full_path).find('src')
            src_path = Path(str(full_path)[:src_idx + 3])
            if src_path.is_dir():
                rel_path = full_path.relative_to(src_path)
                module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')
            else:
                return []
        else:
            return []

    # ⭐ CORREÇÃO: Remove 'src.' do início do nome do módulo se presente
    # Porque a aplicação carrega os módulos como 'model.bookstore.author' e não 'src.model.bookstore.author'
    if module_name.startswith('src.'):
        module_name = module_name[4:]  # Remove 'src.'
        print(f"  🔄 Ajustando nome do módulo: src.model.bookstore.author → {module_name}")

    # ⭐ Estratégia: Usa o módulo já importado ou importa apenas uma vez
    if module_name in sys.modules:
        print(f"  ℹ️ Usando módulo já carregado: {module_name}")
        module = sys.modules[module_name]
    else:
        try:
            print(f"  🔍 Carregando módulo: {module_name}")
            module = importlib.import_module(module_name)
        except Exception as e:
            print(f"  ✗ Erro ao importar {module_name}: {e}")
            return []

    # Coleta todas as classes do módulo que são subclasses de db.Model
    classes = []
    for name, obj in inspect.getmembers(module, inspect.isclass):
        # Verifica se é uma classe definida neste módulo
        if obj.__module__ != module_name:
            continue
        # Ignora classes com 'Trash' no nome
        if "Trash" in name:
            continue
        # Verifica se é um modelo SQLAlchemy
        if not hasattr(obj, "__tablename__"):
            continue
        # Filtra pelo nome da classe se especificado
        if class_name and name != class_name:
            continue
        classes.append((obj, name))

    print(f"  ✅ Encontradas {len(classes)} classes: {[name for _, name in classes]}")
    return classes

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE RENDERIZAÇÃO DE BLOCOS (colunas, filtros, campos)
# ══════════════════════════════════════════════════════════════════════════════

def _build_columns_block(metadata: Dict, model_class=None, relationship_fields: list[dict] | None = None) -> str:
    """
    Gera bloco de ColumnDef(...) para o controller.

    Resolve automaticamente colunas que referenciam relacionamentos FK:
    - "user.username" (com ponto)      → vira "user_username" (Jinja não resolve pontos)
    - "author" (nome puro do relacionamento) → vira "author_name"
    O model NÃO precisa ser editado; a normalização ocorre aqui no gerador.
    Exige que o model tenha @property correspondente (ex: author_name, user_username).
    """
    cols  = metadata.get("ui_listview", {}).get("columns", [])
    rel_names = {r["name"] for r in (relationship_fields or [])}  # ex: {"author_id", "user_id", "book_id"}
    # Nomes de relacionamento sem o sufixo _id (ex: "author", "user", "book")
    rel_bare = {r[:-3] if r.endswith("_id") else r for r in rel_names}

    lines = []
    for c in cols:
        name     = c["name"]
        label    = c.get("label", name)
        sortable = c.get("sortable", False)
        width    = f'"{c["width"]}"' if c.get("width") else "None"
        align    = c.get("align", "start")

        resolved_name = name
        # Caso 1: chave com ponto, ex. "user.username" -> "user_username"
        if "." in name:
            resolved_name = name.replace(".", "_")
            sortable = False  # relacionamento nunca é sortable direto
        # Caso 2: nome puro de relacionamento, ex. "author" -> "author_name"
        elif name in rel_bare or (model_class and hasattr(model_class, name)
                                   and name not in (metadata.get("ui_form", {}).get("fields", []) or [])
                                   and _looks_like_relationship(model_class, name)):
            resolved_name = f"{name}_name"
            sortable = False

        sortable_str = "True" if sortable else "False"
        lines.append(
            f'        ColumnDef("{resolved_name}", "{label}", '
            f'sortable={sortable_str}, width={width}, align="{align}")'
        )
    return ",\n".join(lines) if lines else '        ColumnDef("id", "ID", sortable=True)'


def _looks_like_relationship(model_class, field_name: str) -> bool:
    """Verifica se um atributo do model é um relacionamento SQLAlchemy (não uma coluna)."""
    try:
        from sqlalchemy.orm import RelationshipProperty
        attr = getattr(model_class, field_name, None)
        if attr is None:
            return False
        prop = getattr(attr, "property", None)
        return isinstance(prop, RelationshipProperty)
    except Exception:
        return False


def _build_filters_block(metadata: Dict, model_class=None) -> str:
    """
    Gera bloco de FilterDef(...) para o controller.
    Filtros cujo campo já está marcado com @choices no model são OMITIDOS aqui —
    o controller gerado monta esses dinamicamente via SELECT DISTINCT,
    evitando duplicação visual (dois campos "Gênero" na tela).
    """
    filters = metadata.get("ui_listview", {}).get("filters", [])
    choices_field_names = set()
    if model_class:
        try:
            from annotations import get_choices_fields
            choices_field_names = {ch["field"] for ch in get_choices_fields(model_class)}
        except Exception:
            choices_field_names = set()

    lines = []
    for f in filters:
        name = f["name"]
        if name in choices_field_names:
            continue  # já será gerado dinamicamente como select com @choices
        ftype = f.get("type", "text")
        label = f.get("label", name)
        ph    = f', placeholder="{f["placeholder"]}"' if f.get("placeholder") else ""
        lines.append(f'        FilterDef("{name}", "{label}", type="{ftype}"{ph})')
    return ",\n".join(lines) if lines else '        FilterDef("search", "Buscar", type="text")'


def _build_fields_rows(class_name_lower: str, fields: list[str],
                       relationship_fields: list[dict] | None = None,
                       enum_fields: list[dict] | None = None) -> str:
    """
    Gera linhas <tr> para o detail.html.
    Usa o filtro Jinja |smart_val (registrado em main.py) para:
    - Enum  → .value  (evita 'BookStatus.ACTIVE')
    - ORM   → .name / .title  (evita '<Author ...>')
    - None  → '—'
    - FK    → tenta <field_sem_id>.name primeiro
    """
    fk_names = {r["name"] for r in (relationship_fields or [])}
    rows = []
    for field in fields:
        label = field.replace("_", " ").title()
        if field in fk_names:
            name_attr = field[:-3] if field.endswith("_id") else field
            val_expr  = f"{class_name_lower}.{name_attr}.name if {class_name_lower}.{name_attr} else '—'"
        else:
            val_expr  = f"{class_name_lower}.{field}|smart_val"
        rows.append(
            f"              <tr>\n"
            f"                <th style=\"width:30%\">{label}</th>\n"
            f"                <td>{{{{ {val_expr} }}}}</td>\n"
            f"              </tr>"
        )
    return "\n".join(rows)


def _build_form_fields(fields: list[str], relationship_fields: list[dict] = None,
                       enum_fields: list[dict] = None, model_class=None) -> str:
    """
    Gera campos para o form_modal.
    Detecta automaticamente: FK, Enum, Date e campos obrigatórios (@required).
    """
    from sqlalchemy import DateTime, Date
    from sqlalchemy.orm import ColumnProperty

    fk_names  = {r["name"]: r["foreign_table"] for r in (relationship_fields or [])}
    enum_map  = {e["name"]: e["options"] for e in (enum_fields or [])}

    date_fields: set[str] = set()
    if model_class and hasattr(model_class, "__mapper__"):
        for prop in model_class.__mapper__.iterate_properties:
            if isinstance(prop, ColumnProperty):
                col = prop.columns[0]
                if isinstance(col.type, (DateTime, Date)):
                    date_fields.add(prop.key)

    required_fields: set[str] = set()
    if model_class:
        validations = getattr(model_class, "_validations", {})
        for field_name, rules in validations.items():
            if any(r.get("type") == "required" for r in rules):
                required_fields.add(field_name)

    rows = []
    for field in fields:
        label      = field.replace("_", " ").title()
        req_marker = ' <span class="text-danger">*</span>' if field in required_fields else ""
        req_class  = " required-field" if field in required_fields else ""
        err_div    = f'              <div class="invalid-feedback" id="err-{field}"></div>\n'

        if field in fk_names:
            foreign_table = fk_names[field]
            rows.append(
                f'          <div class="row mb-3 fk-field" data-field="{field}" data-foreign-table="{foreign_table}">\n'
                f'            <label class="col-sm-3 col-form-label">{label}{req_marker}</label>\n'
                f'            <div class="col-sm-9" style="position:relative;">\n'
                f'              <input type="hidden" name="{field}" class="fk-hidden-id">\n'
                f'              <div class="input-group">\n'
                f'                <input type="text" class="form-control fk-search-input{req_class}" data-field-name="{field}" placeholder="Clique ou digite para buscar..." autocomplete="off">\n'
                f'                <button class="btn btn-outline-secondary fk-clear-btn" type="button" title="Limpar">\n'
                f'                  <i class="bi bi-x"></i>\n'
                f'                </button>\n'
                f'              </div>\n'
                f'              <ul class="fk-dropdown list-group position-absolute w-100 shadow" style="z-index:9999;max-height:200px;overflow-y:auto;display:none;top:100%;left:0;"></ul>\n'
                f'{err_div}'
                f'            </div>\n'
                f'          </div>'
            )
        elif field in enum_map:
            options_html = "\n".join(
                f'                    <option value="{v}">{lbl}</option>'
                for v, lbl in enum_map[field]
            )
            rows.append(
                f'          <div class="row mb-3">\n'
                f'            <label for="{field}" class="col-sm-3 col-form-label">{label}{req_marker}</label>\n'
                f'            <div class="col-sm-9">\n'
                f'              <select class="form-select{req_class}" id="{field}" name="{field}" data-field-name="{field}">\n'
                f'                <option value="">Selecione...</option>\n'
                f'{options_html}\n'
                f'              </select>\n'
                f'{err_div}'
                f'            </div>\n'
                f'          </div>'
            )
        elif field in date_fields:
            rows.append(
                f'          <div class="row mb-3">\n'
                f'            <label for="{field}" class="col-sm-3 col-form-label">{label}{req_marker}</label>\n'
                f'            <div class="col-sm-9">\n'
                f'              <input type="date" class="form-control{req_class}" id="{field}" name="{field}" data-field-name="{field}">\n'
                f'{err_div}'
                f'            </div>\n'
                f'          </div>'
            )
        else:
            rows.append(
                f'          <div class="row mb-3">\n'
                f'            <label for="{field}" class="col-sm-3 col-form-label">{label}{req_marker}</label>\n'
                f'            <div class="col-sm-9">\n'
                f'              <input type="text" class="form-control{req_class}" id="{field}" name="{field}" data-field-name="{field}">\n'
                f'{err_div}'
                f'            </div>\n'
                f'          </div>'
            )
    return "\n".join(rows)


def _build_context(
    class_name: str,
    plural: str,
    metadata: Dict,
    model_class=None,
    output_subdir: Path = Path("."),
) -> Dict[str, Any]:
    """Monta o dicionário de contexto passado a todos os templates."""
    class_name_lower = class_name.lower()
    module_name      = metadata.get("module_name", class_name_lower)
    label            = metadata.get("label", class_name)
    default_sort     = metadata.get("ui_listview", {}).get("default_sort", "id")
    form_fields_list = metadata.get("ui_form", {}).get("fields", [])

    # detectar relacionamentos (FK)
    relationship_fields = []
    if model_class:
        relationship_fields = _get_relationship_fields(model_class)

    # detectar campos Enum
    # Suporta tanto SAEnum(MyEnum) quanto String com default PyEnum (padrão do PyTeca)
    enum_fields = []
    if model_class:
        from sqlalchemy.orm import ColumnProperty
        from sqlalchemy import Enum as SAEnum
        from enum import EnumMeta
        for field_name in form_fields_list:
            options = None
            # Abordagem 1: coluna SA Enum nativa (enum_class)
            attr = getattr(model_class, field_name, None)
            if attr is not None and hasattr(attr, 'type'):
                col_type = attr.type
                if isinstance(col_type, SAEnum) and getattr(col_type, 'enum_class', None):
                    enum_class = col_type.enum_class
                    options = [(e.value, e.name.replace('_', ' ').title()) for e in enum_class]
            # Abordagem 2: coluna String com default PyEnum (padrao PyTeca)
            # Detecta inspecionando os defaults e o nome da coluna
            if options is None and model_class.__mapper__:
                for prop in model_class.__mapper__.iterate_properties:
                    if isinstance(prop, ColumnProperty) and prop.key == field_name:
                        col = prop.columns[0]
                        # Procura PyEnum no módulo do modelo
                        import inspect, sys
                        model_module = inspect.getmodule(model_class)
                        for obj_name, obj in vars(model_module).items():
                            if isinstance(obj, EnumMeta) and field_name.replace('_', '').lower() in obj_name.lower():
                                options = [(e.value, e.name.replace('_', ' ').title()) for e in obj]
                                break
            if options:
                enum_fields.append({"name": field_name, "options": options})

    # ============================================================
    # Campos pesquisáveis (searchable_fields) e mapeamento de FKs
    # ============================================================
    searchable_fields = []
    # 1. Prioriza colunas marcadas como filterable nas anotações @listview
    for col in metadata.get("ui_listview", {}).get("columns", []):
        if col.get("filterable"):
            searchable_fields.append(col["name"])

    # 2. Se não houver, tenta campos comuns do model (name, title, username)
    if not searchable_fields and model_class:
        for candidate in ('name', 'title', 'username'):
            if hasattr(model_class, candidate):
                searchable_fields.append(candidate)
                break

    # 3. Fallback: primeiro campo String do model
    if not searchable_fields and model_class:
        for prop in model_class.__mapper__.iterate_properties:
            if hasattr(prop, 'columns') and str(prop.columns[0].type).startswith('VARCHAR'):
                searchable_fields.append(prop.key)
                break

    # Mapeamento de FK -> (model_name, display_field)
    fk_display_map = []
    if model_class and relationship_fields:
        import importlib
        for rel in relationship_fields:
            fk_name = rel['name']
            foreign_table = rel['foreign_table']
            # Converte nome da tabela para nome do model (ex: 'users' -> 'User', 'book' -> 'Book')
            model_name = ''.join(word.capitalize() for word in foreign_table.split('_'))
            if model_name.endswith('s'):
                model_name = model_name[:-1]
            # Tenta importar o model
            module_path = None
            for prefix in ['model.core', 'model.bookstore']:
                try:
                    module = importlib.import_module(f"{prefix}.{model_name.lower()}")
                    model_class_rel = getattr(module, model_name)
                    display_field = getattr(model_class_rel, '_display_field', None)
                    if display_field:
                        module_path = prefix
                        break
                except (ImportError, AttributeError):
                    continue
            if module_path and display_field:
                fk_display_map.append({
                    'fk_name': fk_name,
                    'model_name': model_name,
                    'module_path': module_path,
                    'display_field': display_field
                })

    # ============================================================
    # Geração do bloco de código Python para busca (service)
    # ============================================================
    search_block_lines = []
    if searchable_fields or fk_display_map:
        search_block_lines.append("        if search:")
        search_block_lines.append('            pattern = f"%{search.strip()}%"')
        search_block_lines.append("            from sqlalchemy import or_")
        search_block_lines.append("            search_filters = []")
        # Campos diretos
        for field in searchable_fields:
            search_block_lines.append(f"            search_filters.append({class_name}.{field}.ilike(pattern))")
        # Campos de FKs (joins)
        for fk in fk_display_map:
            search_block_lines.append(f"            from {fk['module_path']}.{fk['model_name'].lower()} import {fk['model_name']}")
            search_block_lines.append(f"            query = query.outerjoin({fk['model_name']}, {class_name}.{fk['fk_name']} == {fk['model_name']}.id)")
            search_block_lines.append(f"            search_filters.append({fk['model_name']}.{fk['display_field']}.ilike(pattern))")
        search_block_lines.append("            if search_filters:")
        search_block_lines.append("                query = query.filter(or_(*search_filters))")
    else:
        # Fallback: busca pelo ID (caso não haja campos pesquisáveis)
        search_block_lines.append("        if search:")
        search_block_lines.append('            pattern = f"%{search.strip()}%"')
        search_block_lines.append(f"            query = query.filter(cast(str({class_name}.id), String).ilike(pattern))")

    search_block = "\n".join(search_block_lines)

    # Monta o dicionário de contexto
    return {
        "class_name":         class_name,
        "class_name_lower":   class_name_lower,
        "module_name":        module_name,
        "plural":             plural,
        "label":              label,
        "default_sort":       default_sort,
        "columns":            _build_columns_block(metadata, model_class, relationship_fields),
        "filters":            _build_filters_block(metadata, model_class),
        "fields_rows":        _build_fields_rows(class_name_lower, form_fields_list, relationship_fields, enum_fields),
        "form_fields":        _build_form_fields(form_fields_list, relationship_fields, enum_fields, model_class),
        "relationship_fields": relationship_fields,
        "enum_fields":        enum_fields,
        "required_fields":    [f for f, rules in getattr(model_class, '_validations', {}).items() if any(r.get('type') == 'required' for r in rules)] if model_class else [],
        "date_fields":        [prop.key for prop in (model_class.__mapper__.iterate_properties if model_class and hasattr(model_class, '__mapper__') else []) if hasattr(prop, 'columns') and hasattr(prop.columns[0].type, '__class__') and prop.columns[0].type.__class__.__name__ in ('DateTime', 'Date')],
        "searchable_fields":  searchable_fields,
        "fk_display_map":     fk_display_map,
        "search_block":       search_block,      
        "output_subdir":      output_subdir,
    }
# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE I/O
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_init_py(directory: Path) -> None:
    init_file = directory / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# Auto-generated\n", encoding="utf-8")
        print(f"  + {init_file}")


def _write_file(path: Path, content: str, overwrite: bool = False) -> bool:
    """Grava arquivo. Retorna True se gravou, False se pulou."""
    if path.exists() and not overwrite:
        print(f"  ⚠  Já existe (pulado): {path}")
        return False
    path.write_text(content, encoding="utf-8")
    action = "atualizado" if path.exists() else "gerado"
    print(f"  ✓ {path}")
    return True


### NÃO APAGAR: ESSAS FUNÇÕES DE GERAÇÃO DE MENU FORAM DESATIVADAS PARA EVITAR SOBRESCRITA INDESEJADA.
###################################################################################################################
#      INICIO - GERAÇÃO DE MENU POR CRUD A PARTIR DE MODELO ANOTADO (CONTROLLER, SERVICE, ROUTES, TEMPLATES)
#                                              DEIXAR DINAMICO
###################################################################################################################
#
# ==================================================================
# GERAÇÃO DO MENU YAML
# ==================================================================
#
###def _generate_menu_yaml(templates_dir: Path, class_name: str, plural: str, label: str, overwrite: bool = False) -> None:
###    """Cria o arquivo menu.yaml na pasta templates/plural se não existir."""
###    menu_yaml_path = templates_dir / "menu.yaml"
###    if menu_yaml_path.exists() and not overwrite:
###        print(f"  ⚠ menu.yaml já existe em {menu_yaml_path}, pulando.")
###        return
###
###    content = f"""# Menu para a seção {label}
###menu:
###  - name: "{label}s"
###    endpoint: "{plural}.list"
###    icon: "bi-grid"
###"""
###    menu_yaml_path.write_text(content, encoding="utf-8")
###    print(f"  ✓ {menu_yaml_path}")
###
###
###def _add_to_root_menu(class_name: str, plural: str, label: str, overwrite: bool = False) -> None:
###    """
###    Adiciona uma entrada para a entidade no menu principal (templates/menu.yaml).
###    Se o arquivo não existir, cria com apenas esta entrada.
###    """
###    root_menu = Path("templates") / "menu.yaml"
###    new_item = {
###        "name": f"{label}s",
###        "endpoint": f"{plural}.list",
###        "icon": "bi-grid"
###    }
###
###    # Carrega o menu existente (se houver)
###    menu_data = {}
###    if root_menu.exists():
###        try:
###            import yaml
###            with open(root_menu, "r", encoding="utf-8") as f:
###                menu_data = yaml.safe_load(f) or {}
###        except Exception as e:
###            print(f"  ⚠ Erro ao ler {root_menu}: {e}")
###
###    # Garante a estrutura
###    if not isinstance(menu_data, dict):
###        menu_data = {}
###    if "menu" not in menu_data or not isinstance(menu_data["menu"], list):
###        menu_data["menu"] = []
###
###    # Verifica se a entrada já existe (pelo endpoint)
###    exists = any(item.get("endpoint") == new_item["endpoint"] for item in menu_data["menu"])
###    if exists and not overwrite:
###        print(f"  ⚠ Entrada para {plural} já existe no menu raiz, pulando.")
###        return
###
###    # Remove entrada antiga se overwrite=True
###    if overwrite:
###        menu_data["menu"] = [item for item in menu_data["menu"] if item.get("endpoint") != new_item["endpoint"]]
###
###    # Adiciona a nova entrada
###    menu_data["menu"].append(new_item)
###
###    # Escreve o arquivo
###    import yaml
###    with open(root_menu, "w", encoding="utf-8") as f:
###        yaml.dump(menu_data, f, allow_unicode=True, sort_keys=False)
###    print(f"  ✓ Entrada adicionada ao menu raiz: {root_menu}")
###################################################################################################################
#      FINAL - GERAÇÃO DE MENU POR CRUD A PARTIR DE MODELO ANOTADO (CONTROLLER, SERVICE, ROUTES, TEMPLATES)
#                                              DEIXAR DINAMICO
###################################################################################################################

# ══════════════════════════════════════════════════════════════════════════════
# DETECÇÃO DE RELACIONAMENTOS (FK)
# ══════════════════════════════════════════════════════════════════════════════

def _get_relationship_fields(model_class) -> list[dict]:
    """
    Retorna metadados das colunas que são chaves estrangeiras.
    Usa sqlalchemy.inspect para garantir detecção correta.
    """
    from sqlalchemy import inspect
    rels = []
    try:
        inspector = inspect(model_class)
        for column in inspector.columns:
            # Verifica se a coluna tem foreign_keys (SQLAlchemy >= 1.4)
            if column.foreign_keys:
                # Obtém a primeira FK (normalmente há apenas uma)
                fk = list(column.foreign_keys)[0]
                rels.append({
                    'name': column.name,
                    'foreign_table': fk.column.table.name,
                    'nullable': column.nullable,
                })
    except Exception as e:
        # Fallback: método antigo
        if hasattr(model_class, '__table__'):
            for col in model_class.__table__.columns:
                if col.foreign_keys:
                    fk = list(col.foreign_keys)[0]
                    rels.append({
                        'name': col.name,
                        'foreign_table': fk.column.table.name,
                        'nullable': col.nullable,
                    })
    return rels



# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE GERAÇÃO (com suporte a subdiretórios)
# ══════════════════════════════════════════════════════════════════════════════

def generate_controller(
    model_file: str,
    class_name: str,
    plural: str,
    metadata: Dict,
    loader,
    overwrite: bool = False,
    model_class=None,
    output_subdir: Path = Path("."),
) -> None:
    base_name = Path(model_file).stem
    output_dir = Path("controller") / output_subdir # / base_name
    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_init_py(output_dir)

    ctx = _build_context(class_name, plural, metadata, model_class=model_class,output_subdir=output_subdir)
    content = loader.render("controller.py.j2", ctx)
    _write_file(output_dir / f"{class_name.lower()}.py", content, overwrite)

    # Hooks pré/pós — criados uma única vez, nunca sobrescritos depois.
    try:
        from utils.hooks_scaffold import ensure_hooks_file, CONTROLLER_HOOKS
        if ensure_hooks_file(output_dir, class_name, class_name.lower(), "controller", CONTROLLER_HOOKS):
            print(f"  🪝 Hooks criados: {output_dir / f'{class_name.lower()}_hooks.py'}")
    except Exception as e:
        print(f"  ⚠  Scaffold de hooks (controller) não aplicado: {e}")


def generate_service(
    model_file: str,
    class_name: str,
    plural: str,
    metadata: Dict,
    loader,
    overwrite: bool = False,
    model_class=None,
    output_subdir: Path = Path("."),
) -> None:
    base_name = Path(model_file).stem
    output_dir = Path("services") / output_subdir #/ base_name
    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_init_py(output_dir)

    ctx = _build_context(class_name, plural, metadata, model_class=model_class,output_subdir=output_subdir)
    content = loader.render("service.py.j2", ctx)
    _write_file(output_dir / f"{class_name.lower()}_service.py", content, overwrite)

    try:
        from utils.hooks_scaffold import ensure_hooks_file, SERVICE_HOOKS
        if ensure_hooks_file(output_dir, class_name, f"{class_name.lower()}_service", "service", SERVICE_HOOKS):
            print(f"  🪝 Hooks criados: {output_dir / f'{class_name.lower()}_service_hooks.py'}")
    except Exception as e:
        print(f"  ⚠  Scaffold de hooks (service) não aplicado: {e}")


def generate_routes(
    model_file: str,
    class_name: str,
    plural: str,
    metadata: Dict,
    loader,
    overwrite: bool = False,
    model_class=None,
    output_subdir: Path = Path("."),
) -> None:
    base_name = Path(model_file).stem
    output_dir = Path("api/routes") / output_subdir #/ base_name
    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_init_py(output_dir)

    ctx = _build_context(class_name, plural, metadata, model_class=model_class, output_subdir=output_subdir)
    content = loader.render("routes.py.j2", ctx)
    _write_file(output_dir / f"{class_name.lower()}_routes.py", content, overwrite)

    try:
        from utils.hooks_scaffold import ensure_hooks_file, ROUTES_HOOKS
        if ensure_hooks_file(output_dir, class_name, f"{class_name.lower()}_routes", "routes (API)", ROUTES_HOOKS):
            print(f"  🪝 Hooks criados: {output_dir / f'{class_name.lower()}_routes_hooks.py'}")
    except Exception as e:
        print(f"  ⚠  Scaffold de hooks (routes) não aplicado: {e}")


def generate_templates(
    model_file: str,
    class_name: str,
    plural: str,
    metadata: Dict,
    loader,
    overwrite: bool = False,
    add_to_root_menu: bool = False,
    model_class=None,
    output_subdir: Path = Path("."),
) -> None:
    # Templates seguem a mesma estrutura aninhada (ex: templates/bookstore/books/)
    templates_dir = Path("templates") / output_subdir / plural
    modals_dir = templates_dir / "_modals"
    templates_dir.mkdir(parents=True, exist_ok=True)
    modals_dir.mkdir(exist_ok=True)

    ctx = _build_context(class_name, plural, metadata, model_class=model_class, output_subdir=output_subdir)

    _write_file(templates_dir / "manage.html",
                loader.render("manage.html.j2", ctx), overwrite)

    _write_file(templates_dir / "detail.html",
                loader.render("detail.html.j2", ctx), overwrite)

    _write_file(modals_dir / f"{class_name.lower()}_form_modal.html",
                loader.render("form_modal.html.j2", ctx), overwrite)

#    _generate_menu_yaml(templates_dir, class_name, plural, ctx["label"], overwrite)

    if add_to_root_menu:
        _add_to_root_menu(class_name, plural, ctx["label"], overwrite)


# ══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

#def _run_generation(
#    file_path: Path,
#    class_name_filter: Optional[str],
#    plural_override: Optional[str],
#    loader,
#    overwrite: bool,
#    add_to_root_menu: bool = False,
#) -> None:
#    """Executa geração para um arquivo de model."""
#    classes = load_classes_from_file(str(file_path), class_name_filter)
#    if not classes:
#        print(f"  ✗ Nenhuma classe db.Model encontrada em {file_path}")
#        return
#
#    # Calcula o subdiretório de saída relativo à pasta 'model'
#    model_root = Path("model")
#    if file_path.parent == model_root:
#        output_subdir = Path(".")
#    else:
#        output_subdir = file_path.parent.relative_to(model_root)
#
#    for cls, cls_name in classes:
#        print(f"\n→ Gerando para {cls_name} ({file_path.name})")
#        metadata = get_model_metadata(cls)
#        metadata["module_name"] = file_path.stem
#        if plural_override:
#            metadata["plural"] = plural_override
#        final_plural = metadata.get("plural", cls_name.lower() + "s")
#
#        generate_controller(str(file_path), cls_name, final_plural, metadata, loader,
#                            overwrite, model_class=cls, output_subdir=output_subdir)
#        generate_service(str(file_path), cls_name, final_plural, metadata, loader,
#                         overwrite, model_class=cls, output_subdir=output_subdir)
#        generate_routes(str(file_path), cls_name, final_plural, metadata, loader,
#                        overwrite, model_class=cls, output_subdir=output_subdir)
#        generate_templates(str(file_path), cls_name, final_plural, metadata, loader,
#                           overwrite, add_to_root_menu, model_class=cls, output_subdir=output_subdir)

def _run_generation(
    file_path: Path,
    class_name_filter: Optional[str],
    plural_override: Optional[str],
    loader,
    overwrite: bool,
    add_to_root_menu: bool = False,
    only: Optional[set] = None,
) -> None:
    """
    Executa geração para um arquivo de model.

    `only` controla quais artefatos gerar. Valores aceitos (como set):
        "controller", "service", "routes", "templates"
    None = gera tudo (comportamento padrão).

    Exemplos via CLI:
        --only controller,service     → só controller e service
        --skip html                   → tudo exceto templates HTML
        --skip controller             → tudo exceto controller
    """
    # Garante que o caminho é absoluto e existente
    file_path = file_path.resolve()
    if not file_path.exists():
        print(f"  ✗ Arquivo não encontrado: {file_path}")
        return

    print(f"  📄 Processando: {file_path}")
    
    # Carrega classes do arquivo
    classes = load_classes_from_file(str(file_path), class_name_filter)
    if not classes:
        return

    # Calcula o subdiretório de saída
    project_root = _find_project_root(file_path)
    if project_root:
        try:
            rel_to_root = file_path.relative_to(project_root)
            # Remove 'model' do início do caminho para obter o subdiretório
            rel_parts = list(rel_to_root.parts)
            if 'model' in rel_parts:
                model_idx = rel_parts.index('model')
                sub_parts = rel_parts[model_idx + 1:-1]  # remove model/ e o nome do arquivo
                output_subdir = Path(*sub_parts) if sub_parts else Path(".")
            else:
                output_subdir = Path(".")
        except ValueError:
            output_subdir = Path(".")
    else:
        output_subdir = Path(".")

    print(f"  📁 Subdiretório de saída: {output_subdir}")

    for cls, cls_name in classes:
        print(f"\n→ Gerando para {cls_name} ({file_path.name})")
        metadata = get_model_metadata(cls)
        metadata["module_name"] = file_path.stem
        if plural_override:
            metadata["plural"] = plural_override
        final_plural = metadata.get("plural", cls_name.lower() + "s")

        # ── Sincronização de permissões (Camada 1 + Camada 2) ──────────────
        # Código lidera, banco segue: nunca cria nada manualmente via UI.
        # Falha em sincronizar nunca bloqueia a geração do CRUD em si.
        try:
            from utils.permissions_sync import sync_model_permissions
            sync_model_permissions(cls, final_plural)
        except Exception as e:
            print(f"  ⚠  Sincronização de permissões não aplicada: {e}")

        _all = only is None
        if _all or "controller" in only:
            generate_controller(str(file_path), cls_name, final_plural, metadata, loader,
                                overwrite, model_class=cls, output_subdir=output_subdir)
        if _all or "service" in only:
            generate_service(str(file_path), cls_name, final_plural, metadata, loader,
                             overwrite, model_class=cls, output_subdir=output_subdir)
        if _all or "routes" in only:
            generate_routes(str(file_path), cls_name, final_plural, metadata, loader,
                            overwrite, model_class=cls, output_subdir=output_subdir)
        if _all or "templates" in only:
            generate_templates(str(file_path), cls_name, final_plural, metadata, loader,
                               overwrite, add_to_root_menu, model_class=cls, output_subdir=output_subdir)

def generate_from_config() -> None:
    """Gera CRUDs para todos os modelos listados em config.yaml."""
    config = load_config()
    generator_cfg = config.get("generator", {})
    overwrite = generator_cfg.get("overwrite", False)
    theme = generator_cfg.get("template_theme", "standard")
    loader = get_loader(theme)

    print(f"Tema de templates: '{theme}'  |  overwrite={overwrite}")

    for entry in config.get("models", []):
        source = entry.get("source", "")
        file_path = Path(source)
        if not file_path.exists():
            print(f"  ✗ Arquivo não encontrado: {file_path}")
            continue

        add_to_root_menu = entry.get("add_to_root_menu", False)

        _run_generation(
            file_path,
            class_name_filter=entry.get("class_name"),
            plural_override=entry.get("plural"),
            loader=loader,
            overwrite=overwrite,
            add_to_root_menu=add_to_root_menu,
        )


def generate(
    model_path: str,
    theme: str = "standard",
    overwrite: bool = False,
    add_to_root_menu: bool = False,
    only: Optional[set] = None,
) -> None:
    """
    Gera artefatos para um único arquivo de model.

    Parâmetros:
        model_path      — caminho para o model (ex: "model/bookstore/book.py")
        theme           — pasta de templates (padrão: "standard")
        overwrite       — sobrescreve arquivos já existentes
        add_to_root_menu — adiciona entrada no menu raiz
        only            — set com os artefatos a gerar:
                          {"controller", "service", "routes", "templates"}
                          None (padrão) = gera todos
    """
    file_path = Path(model_path)
    if not file_path.exists():
        print(f"  ✗ Arquivo não encontrado: {file_path}")
        return

    loader = get_loader(theme)
    if only:
        print(f"Tema: '{theme}'  |  overwrite={overwrite}  |  only={sorted(only)}")
    else:
        print(f"Tema de templates: '{theme}'  |  overwrite={overwrite}")
    _run_generation(file_path, None, None, loader, overwrite,
                    add_to_root_menu=add_to_root_menu, only=only)

    try:
        from api.routes.core.options_routes import refresh_options_cache
        refresh_options_cache()
        print("Cache de opções recarregado.")
    except Exception as e:
        print(f"Não foi possível recarregar o cache: {e}")
