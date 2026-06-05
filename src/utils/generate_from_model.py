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
    Carrega todas as classes de um arquivo Python que são subclasses de db.Model
    e cujo nome não contenha 'Trash'.
    Retorna lista de (cls, nome_da_classe).
    Usa importação real (com nome completo) para resolver dependências.
    """
    import sys
    import importlib

    full_path = Path(file_path).resolve()
    project_root = full_path.parent.parent  # assume que 'src' é a raiz do projeto

    # Adiciona a raiz do projeto ao sys.path para permitir imports absolutos
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Calcula o nome do módulo a partir do caminho relativo à raiz
    rel_path = full_path.relative_to(project_root)
    module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')

    # Remove do cache se já existir (força recarga)
    if module_name in sys.modules:
        del sys.modules[module_name]

    try:
        module = importlib.import_module(module_name)
    except Exception as e:
        print(f"Erro ao importar {module_name}: {e}")
        return []

    classes = []
    for name, obj in module.__dict__.items():
        if not isinstance(obj, type):
            continue
        # Ignora classes importadas de outros módulos
        if obj.__module__ != module.__name__:
            continue
        if "Trash" in name:
            continue
        if not (hasattr(obj, "__tablename__") or
                any(hasattr(b, "__name__") and b.__name__ == "Model"
                    for b in getattr(obj, "__bases__", []))):
            continue
        if class_name and name != class_name:
            continue
        classes.append((obj, name))

    return classes


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE RENDERIZAÇÃO DE BLOCOS (colunas, filtros, campos)
# ══════════════════════════════════════════════════════════════════════════════

def _build_columns_block(metadata: Dict) -> str:
    """Gera bloco de ColumnDef(...) para o controller."""
    cols  = metadata.get("ui_listview", {}).get("columns", [])
    lines = []
    for c in cols:
        name     = c["name"]
        label    = c.get("label", name)
        sortable = "True" if c.get("sortable") else "False"
        width    = f'"{c["width"]}"' if c.get("width") else "None"
        align    = c.get("align", "start")
        lines.append(
            f'        ColumnDef("{name}", "{label}", '
            f'sortable={sortable}, width={width}, align="{align}")'
        )
    return ",\n".join(lines) if lines else '        ColumnDef("id", "ID", sortable=True)'


def _build_filters_block(metadata: Dict) -> str:
    """Gera bloco de FilterDef(...) para o controller."""
    filters = metadata.get("ui_listview", {}).get("filters", [])
    lines   = []
    for f in filters:
        name  = f["name"]
        ftype = f.get("type", "text")
        label = f.get("label", name)
        ph    = f', placeholder="{f["placeholder"]}"' if f.get("placeholder") else ""
        lines.append(f'        FilterDef("{name}", "{label}", type="{ftype}"{ph})')
    return ",\n".join(lines) if lines else '        FilterDef("search", "Buscar", type="text")'


def _build_fields_rows(class_name_lower: str, fields: list[str]) -> str:
    """Gera linhas <tr> para o detail.html."""
    rows = []
    for field in fields:
        label = field.replace("_", " ").title()
        rows.append(
            f"              <td>\n"
            f"                <th style=\"width:30%\">{label}</th>\n"
            f"                <td>{{{{ {class_name_lower}.{field} or '—' }}}}</td>\n"
            f"              </tr>"
        )
    return "\n".join(rows)


def _build_form_fields(fields: list[str]) -> str:
    """Gera campos <div class='mb-3'> para o form_modal."""
    rows = []
    for field in fields:
        label = field.replace("_", " ").title()
        rows.append(
            f'          <div class="row mb-3">\n'
            f'            <label for="{field}" class="col-sm-3 col-form-label">{label}</label>\n'
            f'            <div class="col-sm-9">\n'
            f'              <input type="text" class="form-control" id="{field}" name="{field}">\n'
            f'            </div>\n'
            f'          </div>'
        )
    return "\n".join(rows)


def _build_context(
    class_name: str,
    plural: str,
    metadata: Dict,
    model_class=None,
) -> Dict[str, Any]:
    """Monta o dicionário de contexto passado a todos os templates."""
    class_name_lower = class_name.lower()
    module_name      = metadata.get("module_name", class_name_lower)
    label            = metadata.get("label", class_name)
    default_sort     = metadata.get("ui_listview", {}).get("default_sort", "id")
    form_fields_list = metadata.get("ui_form", {}).get("fields", [])
    # detectar relacionamentos
    relationship_fields = []
    if model_class:
        relationship_fields = _get_relationship_fields(model_class)

    return {
        "class_name":       class_name,
        "class_name_lower": class_name_lower,
        "module_name":      module_name,
        "plural":           plural,
        "label":            label,
        "default_sort":     default_sort,
        "columns":          _build_columns_block(metadata),
        "filters":          _build_filters_block(metadata),
        "fields_rows":      _build_fields_rows(class_name_lower, form_fields_list),
        "form_fields":      _build_form_fields(form_fields_list),
        "relationship_fields": relationship_fields, 
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

# ==================================================================
# GERAÇÃO DO MENU YAML
# ==================================================================

def _generate_menu_yaml(templates_dir: Path, class_name: str, plural: str, label: str, overwrite: bool = False) -> None:
    """Cria o arquivo menu.yaml na pasta templates/plural se não existir."""
    menu_yaml_path = templates_dir / "menu.yaml"
    if menu_yaml_path.exists() and not overwrite:
        print(f"  ⚠ menu.yaml já existe em {menu_yaml_path}, pulando.")
        return

    content = f"""# Menu para a seção {label}
menu:
  - name: "{label}s"
    endpoint: "{plural}.list"
    icon: "bi-grid"
"""
    menu_yaml_path.write_text(content, encoding="utf-8")
    print(f"  ✓ {menu_yaml_path}")


def _add_to_root_menu(class_name: str, plural: str, label: str, overwrite: bool = False) -> None:
    """
    Adiciona uma entrada para a entidade no menu principal (templates/menu.yaml).
    Se o arquivo não existir, cria com apenas esta entrada.
    """
    root_menu = Path("templates") / "menu.yaml"
    new_item = {
        "name": f"{label}s",
        "endpoint": f"{plural}.list",
        "icon": "bi-grid"
    }

    # Carrega o menu existente (se houver)
    menu_data = {}
    if root_menu.exists():
        try:
            import yaml
            with open(root_menu, "r", encoding="utf-8") as f:
                menu_data = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"  ⚠ Erro ao ler {root_menu}: {e}")

    # Garante a estrutura
    if not isinstance(menu_data, dict):
        menu_data = {}
    if "menu" not in menu_data or not isinstance(menu_data["menu"], list):
        menu_data["menu"] = []

    # Verifica se a entrada já existe (pelo endpoint)
    exists = any(item.get("endpoint") == new_item["endpoint"] for item in menu_data["menu"])
    if exists and not overwrite:
        print(f"  ⚠ Entrada para {plural} já existe no menu raiz, pulando.")
        return

    # Remove entrada antiga se overwrite=True
    if overwrite:
        menu_data["menu"] = [item for item in menu_data["menu"] if item.get("endpoint") != new_item["endpoint"]]

    # Adiciona a nova entrada
    menu_data["menu"].append(new_item)

    # Escreve o arquivo
    import yaml
    with open(root_menu, "w", encoding="utf-8") as f:
        yaml.dump(menu_data, f, allow_unicode=True, sort_keys=False)
    print(f"  ✓ Entrada adicionada ao menu raiz: {root_menu}")

# ══════════════════════════════════════════════════════════════════════════════
# DETECÇÃO DE RELACIONAMENTOS (FK)
# ══════════════════════════════════════════════════════════════════════════════

def _get_relationship_fields(model_class) -> list[dict]:
    """
    Retorna metadados das colunas que são chaves estrangeiras.
    Cada entrada contém: name, foreign_table, nullable.
    """
    rels = []
    if not hasattr(model_class, '__table__'):
        return rels
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

    ctx = _build_context(class_name, plural, metadata, model_class=model_class)
    content = loader.render("controller.py.j2", ctx)
    _write_file(output_dir / f"{class_name.lower()}.py", content, overwrite)


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

    ctx = _build_context(class_name, plural, metadata, model_class=model_class)
    content = loader.render("service.py.j2", ctx)
    _write_file(output_dir / f"{class_name.lower()}_service.py", content, overwrite)


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

    ctx = _build_context(class_name, plural, metadata, model_class=model_class)
    content = loader.render("routes.py.j2", ctx)
    _write_file(output_dir / f"{class_name.lower()}_routes.py", content, overwrite)


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

    ctx = _build_context(class_name, plural, metadata, model_class=model_class)

    _write_file(templates_dir / "manage.html",
                loader.render("manage.html.j2", ctx), overwrite)

    _write_file(templates_dir / "detail.html",
                loader.render("detail.html.j2", ctx), overwrite)

    _write_file(modals_dir / f"{class_name.lower()}_form_modal.html",
                loader.render("form_modal.html.j2", ctx), overwrite)

    _generate_menu_yaml(templates_dir, class_name, plural, ctx["label"], overwrite)

    if add_to_root_menu:
        _add_to_root_menu(class_name, plural, ctx["label"], overwrite)


# ══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def _run_generation(
    file_path: Path,
    class_name_filter: Optional[str],
    plural_override: Optional[str],
    loader,
    overwrite: bool,
    add_to_root_menu: bool = False,
) -> None:
    """Executa geração para um arquivo de model."""
    classes = load_classes_from_file(str(file_path), class_name_filter)
    if not classes:
        print(f"  ✗ Nenhuma classe db.Model encontrada em {file_path}")
        return

    # Calcula o subdiretório de saída relativo à pasta 'model'
    model_root = Path("model")
    if file_path.parent == model_root:
        output_subdir = Path(".")
    else:
        output_subdir = file_path.parent.relative_to(model_root)

    for cls, cls_name in classes:
        print(f"\n→ Gerando para {cls_name} ({file_path.name})")
        metadata = get_model_metadata(cls)
        metadata["module_name"] = file_path.stem
        if plural_override:
            metadata["plural"] = plural_override
        final_plural = metadata.get("plural", cls_name.lower() + "s")

        generate_controller(str(file_path), cls_name, final_plural, metadata, loader,
                            overwrite, model_class=cls, output_subdir=output_subdir)
        generate_service(str(file_path), cls_name, final_plural, metadata, loader,
                         overwrite, model_class=cls, output_subdir=output_subdir)
        generate_routes(str(file_path), cls_name, final_plural, metadata, loader,
                        overwrite, model_class=cls, output_subdir=output_subdir)
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


def generate(model_path: str, theme: str = "standard", overwrite: bool = False, add_to_root_menu: bool = False) -> None:
    """
    Gera todos os artefatos para um único arquivo de model.
    Exemplo: generate("model/author.py") ou generate("model/bookstore/loan.py")
    """
    file_path = Path(model_path)
    if not file_path.exists():
        print(f"  ✗ Arquivo não encontrado: {file_path}")
        return

    loader = get_loader(theme)
    print(f"Tema de templates: '{theme}'  |  overwrite={overwrite}")
    _run_generation(file_path, None, None, loader, overwrite, add_to_root_menu=add_to_root_menu)