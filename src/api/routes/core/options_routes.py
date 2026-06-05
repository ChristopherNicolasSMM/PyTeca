from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy import or_

from db.database import db
from model.core.user import User
from model.bookstore.book import Book

options_bp = Blueprint("options", __name__, url_prefix="/api/options")

# Mapeamento: nome da tabela -> (model, campos de busca, função de exibição)
TABLE_MAP = {
    "users": {
        "model": User,
        "search_fields": ["username", "email"],
        "display": lambda u: f"{u.username} ({u.email})"
    },
    "book": {
        "model": Book,
        "search_fields": ["title", "author"],
        "display": lambda b: f"{b.title} - {b.author}"
    },
    # Adicione outras tabelas conforme necessário
}

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

    if table_name not in TABLE_MAP:
        return jsonify({"error": "Tabela não suportada"}), 400

    cfg = TABLE_MAP[table_name]
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