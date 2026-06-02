from __future__ import annotations
from pathlib import Path
import yaml
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from model.book import BookStatus
from services.book_service import book_service
from utils.crud_loader import load_crud_config

book_bp = Blueprint("books", __name__, url_prefix="/books")

# ── Listagem (agora usando manage.html com mode=list) ─────────────────────
@book_bp.route("/")
@login_required
def list_books():
    crud_config = load_crud_config('books') 

    status = request.args.get("status", BookStatus.ACTIVE)
    search = request.args.get("search", "").strip() or None
    genre = request.args.get("genre", "").strip() or None
    sort = request.args.get("sort", "title")
    direction = request.args.get("dir", "asc")
    page = int(request.args.get("page", 1))
    
    # Usa per_page do YAML ou padrão 20
    per_page = int(request.args.get(
        "per_page", 
        crud_config.get('list', {}).get('pagination', {}).get('default_per_page', 20)
    ))

    result = book_service.list_books(
        page=page, per_page=per_page, status=status,
        search=search, genre=genre, sort=sort, direction=direction,
    )

    genres = book_service.get_genres()
    counts = book_service.count_by_status()

    return render_template(
        "books/manage.html",
        crud_config=crud_config,
        mode="list",
        books=result.items,
        pagination=result,
        genres=genres,
        counts=counts,
        current_status=status,
        current_search=search or "",
        current_genre=genre or "",
        current_sort=sort,
        current_dir=direction,
    )

# ── Detalhe (agora usando manage.html com mode=detail) ───────────────────
@book_bp.route("/<int:book_id>")
@login_required
def detail(book_id: int):
    crud_config = load_crud_config('books')
    book = book_service.get_by_id(book_id)
    if not book:
        abort(404)
    return render_template("books/manage.html", crud_config=crud_config, mode="detail", book=book)

# ── Novo livro (rascunho) ───────────────────────────────────────────────
@book_bp.route("/new")
@login_required
def new_book():
    result = book_service.create_draft()
    draft = result.data
    return redirect(url_for("books.edit_book", book_id=draft.id))

# ── Edição (agora usando manage.html com mode=form) ─────────────────────
@book_bp.route("/<int:book_id>/edit")
@login_required
def edit_book(book_id: int):
    crud_config = load_crud_config('books')
    book = book_service.get_by_id(book_id)
    if not book:
        abort(404)
    if book.is_trashed:
        flash("Este livro está na lixeira. Restaure-o para editar.", "warning")
        return redirect(url_for("books.list_books", status="trash"))
    return render_template("books/manage.html", crud_config=crud_config, mode="form", book=book)


# ── Ações POST (exatamente iguais, só mudar redirect para list_books) ───
@book_bp.route("/<int:book_id>/trash", methods=["POST"])
@login_required
def trash_book(book_id: int):
    result = book_service.trash(book_id)
    if result.success:
        flash("Livro movido para a lixeira.", "success")
    else:
        flash(result.error, "danger")
    return redirect(url_for("books.list_books"))

@book_bp.route("/<int:book_id>/restore", methods=["POST"])
@login_required
def restore_book(book_id: int):
    result = book_service.restore(book_id)
    if result.success:
        flash("Livro restaurado com sucesso.", "success")
    else:
        flash(result.error, "danger")
    return redirect(url_for("books.list_books", status="trash"))

@book_bp.route("/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id: int):
    if not current_user.is_admin:
        abort(403)
    result = book_service.delete_permanent(book_id)
    if result.success:
        flash("Livro excluído permanentemente.", "success")
    else:
        flash(result.error, "danger")
    return redirect(url_for("books.list_books", status="trash"))

@book_bp.route("/<int:book_id>/discard", methods=["POST"])
@login_required
def discard_draft(book_id: int):
    result = book_service.discard_draft(book_id)
    if result.success:
        flash("Rascunho descartado.", "info")
    else:
        flash(result.error, "danger")
    return redirect(url_for("books.list_books"))

# ── Rota para processar o formulário (criar/atualizar) ───────────────────
# Adicione esta rota se ainda não existir – ela será chamada pelo FORM
@book_bp.route("/save", methods=["POST"])
@login_required
def save_book():
    data = request.form.to_dict()
    book_id = data.pop("book_id", None)
    if book_id:
        result = book_service.update(book_id, data)
    else:
        result = book_service.create(data)
    if result.success:
        flash("Livro salvo com sucesso.", "success")
    else:
        flash(result.error, "danger")
    return redirect(url_for("books.list_books"))