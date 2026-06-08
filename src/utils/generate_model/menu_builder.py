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

def apply_menu_customization(items: list[dict], config: dict) -> list[dict]:
    """
    Aplica customizações definidas no banco sobre a lista de itens do menu.
    
    Configurações suportadas:
    - Se config tiver a chave "full_menu", substitui completamente a lista.
    - Caso contrário, aplica overrides:
        - "hide": lista de endpoints a serem removidos.
        - "rename": dicionário {endpoint: novo_nome}.
        - "move": dicionário {endpoint: novo_parent} (move para outro pai).
        - "reorder": lista de endpoints na ordem desejada (para itens raiz).
        - "icon_change": dicionário {endpoint: novo_icon}.
    """
    # 1. Substituição total (se for o caso)
    if "full_menu" in config and isinstance(config["full_menu"], list):
        return config["full_menu"]

    # 2. Overrides parciais
    hide_set = set(config.get("hide", []))
    rename_map = config.get("rename", {})
    move_map = config.get("move", {})
    icon_map = config.get("icon_change", {})
    reorder_root = config.get("reorder", [])

    # Filtrar itens ocultos
    filtered = [item for item in items if item.get("endpoint") not in hide_set]

    # Renomear e trocar ícones
    for item in filtered:
        ep = item.get("endpoint")
        if ep in rename_map:
            item["name"] = rename_map[ep]
        if ep in icon_map:
            item["icon"] = icon_map[ep]

    # Mover itens (alterar parent)
    for item in filtered:
        ep = item.get("endpoint")
        if ep in move_map:
            item["parent"] = move_map[ep]

    # Reordenar itens raiz (apenas os que estão no nível superior, sem parent definido)
    if reorder_root:
        root_items = [item for item in filtered if not item.get("parent")]
        other_items = [item for item in filtered if item.get("parent")]
        # Ordenar root_items conforme a ordem em reorder_root (preservando os não listados no final)
        ordered = []
        for ep in reorder_root:
            for item in root_items:
                if item.get("endpoint") == ep and item not in ordered:
                    ordered.append(item)
        # Adicionar os que sobraram (não listados) mantendo ordem original
        for item in root_items:
            if item not in ordered:
                ordered.append(item)
        filtered = ordered + other_items

    return filtered

#def get_full_menu() -> list[dict]:
def get_full_menu(user_id=None):
    # 1. Verificar se existe customização salva (prioridade máxima)
    from model.core.config.menu_customization import MenuCustomization
    custom = None
    if user_id:
        custom = MenuCustomization.query.filter_by(user_id=user_id).first()
    if not custom:
        custom = MenuCustomization.query.filter_by(user_id=None).first()
    
    if custom and custom.config:
        # Se a customização tiver uma lista completa, usa direto
        if "full_menu" in custom.config:
            return build_tree(custom.config["full_menu"])
        else:
            # Caso contrário, monta a lista normal e aplica os overrides
            all_items = []
            all_items.extend(get_registered_items())
            all_items.extend(get_items_from_yaml())
            all_items.extend(get_items_from_models())
            all_items = apply_menu_customization(all_items, custom.config)
            return build_tree(all_items)

    # 2. Sem customização: fluxo original
    all_items = []
    all_items.extend(get_registered_items())
    all_items.extend(get_items_from_yaml())
    all_items.extend(get_items_from_models())
    return build_tree(all_items)

