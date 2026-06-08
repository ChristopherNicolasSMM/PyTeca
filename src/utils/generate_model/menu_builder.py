# src/utils/menu_builder.py
from __future__ import annotations

import yaml
from pathlib import Path
from flask import url_for, current_app, request
from db.database import db
from annotations import get_model_metadata

# ------------------------------------------------------------
# Registro global para itens adicionados via decorator
# ------------------------------------------------------------
_registered_menu_items = []

def register_menu_item(item: dict):
    _registered_menu_items.append(item)

def get_registered_items() -> list[dict]:
    return _registered_menu_items.copy()

def menu_item(name: str, icon: str = "bi-grid", endpoint: str = None, parent: str = None, **kwargs):
    """
    Decorator para registrar uma view como item de menu.

    Args:
        name: Nome exibido no menu.
        icon: Classe do ícone (Bootstrap Icons). Ex: 'bi-speedometer2'.
        endpoint: Nome do endpoint Flask (obrigatório para views em blueprints).
                 Para funções sem blueprint, pode ser omitido (usa o nome da função).
                 Ex: 'web.dashboard', 'auth.login'.
        parent: Endpoint ou 'name' do item pai (para criar submenu).
        **kwargs: Campos adicionais (ex: order, roles_allowed).

    Importante:
        - Se a view estiver dentro de um Blueprint, **é obrigatório** informar o `endpoint`
          completo no formato `blueprint.nome_da_funcao`.
        - O sistema não infere automaticamente o prefixo do blueprint.
        - Exemplo correto:
            @web_bp.route("/dashboard")
            @menu_item("Dashboard", icon="bi-speedometer2", endpoint="web.dashboard")
            def dashboard(): ...
    """
    def decorator(view_func):
        nonlocal endpoint
        if endpoint is None:
            # Para funções sem blueprint, usa o nome da função como endpoint
            endpoint = view_func.__name__
            # Aviso em desenvolvimento para lembrar o usuário
            import sys
            if hasattr(sys, 'gettrace') and sys.gettrace() is not None:
                print(f"[menu_item] Aviso: endpoint não informado para '{name}'. "
                      f"Usando '{endpoint}'. Se estiver em um blueprint, especifique o endpoint completo.")
        register_menu_item({
            "name": name,
            "endpoint": endpoint,
            "icon": icon,
            "parent": parent,
            **kwargs
        })
        return view_func
    return decorator
#def menu_item(name: str, icon: str = "bi-grid", endpoint: str = None, parent: str = None, **kwargs):
#    """
#    Decorator para registrar uma view como item de menu.
#    parent: endpoint ou name do item pai (para criar submenu)
#    """
#    def decorator(view_func):
#        nonlocal endpoint
#        if endpoint is None:
#            endpoint = view_func.__name__
#        register_menu_item({
#            "name": name,
#            "endpoint": endpoint,
#            "icon": icon,
#            "parent": parent,
#            **kwargs
#        })
#        return view_func
#    return decorator

# ------------------------------------------------------------
# Itens gerados a partir dos modelos anotados
# ------------------------------------------------------------
def get_items_from_models() -> list[dict]:
    items = []
    for model_class in db.Model.__subclasses__():
        if not hasattr(model_class, '__tablename__'):
            continue
        meta = get_model_metadata(model_class)
        label = meta.get('label')
        plural = meta.get('plural')
        if not label or not plural:
            continue
        endpoint = f"{plural}.list"
        try:
            url_for(endpoint)
        except Exception:
            continue
        icon = getattr(model_class, '_menu_icon', 'bi-grid')
        # parent pode ser definido via anotação @menu_parent futuramente
        parent = getattr(model_class, '_menu_parent', None)
        items.append({
            "name": label,
            "endpoint": endpoint,
            "icon": icon,
            "parent": parent,
        })
    return items

# ------------------------------------------------------------
# Itens extras do arquivo YAML (templates/menu.yaml)
# ------------------------------------------------------------
def get_items_from_yaml() -> list[dict]:
    # Sobe do diretório atual (utils/generate_model) até a raiz do projeto (src) e então entra em templates
    yaml_path = Path(__file__).parent.parent.parent / "templates" / "menu_complementar.yaml"
    if not yaml_path.exists():
        print(f"[menu_builder] Arquivo de menu complementar não encontrado: {yaml_path}. Ignorando.")
        return []
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    # Aceita tanto 'items' (lista plana) quanto 'extra_items' (back compat)
    items = data.get('items', data.get('extra_items', []))
    # Itens podem ter campo 'parent'
    print(f"[menu_builder] Carregados {len(items)} itens do YAML complementar.")
    return items

# ------------------------------------------------------------
# Construção da árvore e remoção de duplicatas
# ------------------------------------------------------------
def build_tree(items: list[dict]) -> list[dict]:
    """
    Constrói uma árvore de menus a partir de uma lista plana.
    Cada item pode ter 'parent' (endpoint ou name do pai).
    Itens sem 'parent' ficam no nível raiz.
    Duplicatas (mesmo endpoint) são resolvidas: a primeira ocorrência vence.
    """
    # 1. Remover duplicatas baseado em endpoint
    unique = {}
    for item in items:
        ep = item.get('endpoint')
        if ep and ep not in unique:
            unique[ep] = item
        elif not ep:
            # itens sem endpoint também podem ser pais (grupos)
            unique.setdefault(id(item), item)  # fallback
    unique_items = list(unique.values())

    # 2. Mapear cada item pelo seu identificador (endpoint ou name)
    by_endpoint = {item['endpoint']: item for item in unique_items if item.get('endpoint')}
    by_name = {item['name']: item for item in unique_items}

    # 3. Construir árvore
    tree = []
    for item in unique_items:
        parent_ref = item.get('parent')
        if parent_ref:
            parent = by_endpoint.get(parent_ref) or by_name.get(parent_ref)
            if parent:
                parent.setdefault('children', []).append(item)
                continue
            # Se o pai não foi encontrado, coloca na raiz (opcional: log warning)
        tree.append(item)

    # 4. Ordenar cada nível por ordem customizada ou nome
    def sort_key(x):
        return x.get('order', 999), x.get('name', '')
    tree.sort(key=sort_key)
    for item in tree:
        if 'children' in item:
            item['children'].sort(key=sort_key)
    return tree

# ------------------------------------------------------------
# Função principal que consolida todas as fontes
# ------------------------------------------------------------
def get_full_menu() -> list[dict]:
    all_items = []
    all_items.extend(get_registered_items())      # 1º manual (decorator)
    all_items.extend(get_items_from_yaml())       # 2º YAML
    all_items.extend(get_items_from_models())     # 3º automático
    return build_tree(all_items)

