from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy import or_, inspect
from db.database import db
from annotations import get_model_metadata

options_bp = Blueprint("options", __name__, url_prefix="/api/options")

# Cache para o mapeamento (recriado na inicialização ou sob demanda)
_options_cache = None

def _get_display_field(model_class):
    """Retorna o nome do campo que deve ser usado para exibição."""
    # Prioridade: anotação @display_field
    meta = get_model_metadata(model_class)
    display = meta.get('display_field')
    if display:
        return display
    # Se não houver, tenta campos comuns
    common = ['name', 'title', 'username']
    for cand in common:
        if hasattr(model_class, cand):
            return cand
    # Fallback: primeiro campo String
    for col in inspect(model_class).columns:
        if str(col.type).startswith('VARCHAR'):
            return col.name
    return 'id'

def _get_search_fields(model_class):
    """Retorna lista de campos pesquisáveis para o modelo."""
    # Prioridade: colunas marcadas como filterable no @listview
    meta = get_model_metadata(model_class)
    ui_listview = meta.get('ui_listview')
    if ui_listview and ui_listview.get('filters'):
        # Extrai campos que são do tipo 'text' (busca textual)
        # Mas pode ser simplificado: usar todos os filterable das colunas
        pass
    # Fallback: campos comuns
    common = ['name', 'title', 'username', 'email']
    search_fields = [f for f in common if hasattr(model_class, f)]
    if not search_fields:
        # Usa o primeiro campo String
        for col in inspect(model_class).columns:
            if str(col.type).startswith('VARCHAR'):
                search_fields = [col.name]
                break
    return search_fields

def _build_options_map():
    """Constrói o mapeamento de todas as tabelas (modelos) disponíveis."""
    mapping = {}
    for model_class in db.Model.__subclasses__():
        # Ignora modelos que não tenham tabela (ex: classes abstratas) ou que contenham 'Trash'
        if not hasattr(model_class, '__tablename__'):
            continue
        if 'Trash' in model_class.__name__:
            continue
        table_name = model_class.__tablename__
        display_field = _get_display_field(model_class)
        search_fields = _get_search_fields(model_class)

        # Função de display genérica
        def display_func(obj, field=display_field):
            val = getattr(obj, field, None)
            if val is None:
                return f"{obj.__class__.__name__} #{obj.id}"
            return str(val)

        mapping[table_name] = {
            "model": model_class,
            "search_fields": search_fields,
            "display": display_func
        }
    return mapping

def get_options_map():
    """Retorna o mapa de opções com cache."""
    global _options_cache
    if _options_cache is None:
        _options_cache = _build_options_map()
    return _options_cache

def refresh_options_cache():
    """Força a recarga do cache (útil após gerar novos modelos)."""
    global _options_cache
    _options_cache = _build_options_map()
    return _options_cache

@options_bp.route("/refresh", methods=["POST"])
@login_required
def refresh_cache():
    """Endpoint administrativo para recarregar o cache de opções."""
    # Opcional: só permitir para admin
    from flask_login import current_user
    if not getattr(current_user, 'is_admin', False):
        return jsonify({"error": "Apenas administradores"}), 403
    refresh_options_cache()
    return jsonify({"success": True, "tables": list(get_options_map().keys())})

@options_bp.route("/<string:table_name>")
@login_required
def get_options(table_name):
    """
    Retorna opções paginadas para um campo de seleção.
    Query params: ?search=xxx&page=1
    Resposta: { results: [{id, text}], pagination: {more: bool} }
    """
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 20

    mapping = get_options_map()
    if table_name not in mapping:
        return jsonify({"error": f"Tabela '{table_name}' não suportada"}), 400

    cfg = mapping[table_name]
    model = cfg["model"]
    query = model.query
    if search:
        filters = []
        for field in cfg["search_fields"]:
            filters.append(getattr(model, field).ilike(f"%{search}%"))
        query = query.filter(or_(*filters))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    results = [
        {"id": item.id, "text": cfg["display"](item)}
        for item in pagination.items
    ]
    return jsonify({
        "results": results,
        "pagination": {"more": pagination.has_next}
    })