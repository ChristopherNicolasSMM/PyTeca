import pytest
import os
import json
from datetime import datetime
from sqlalchemy.exc import IntegrityError

# Define a variável de ambiente para garantir que o database.py não bloqueie a execução
os.environ['FLASK_ENV'] = 'DEV'

# ==========================================
# FIXTURES DE CONFIGURAÇÃO (FLASK + DB)
# ==========================================

@pytest.fixture(scope='module')
def app():
    """Configura a aplicação Flask e garante que os modelos sejam carregados."""
    from main import create_app
    from model.book import Book, BookTrash
    
    flask_app = create_app()
    
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False
    })

    with flask_app.app_context():
        from db.database import db
        db.create_all() # Cria as tabelas na memória
        yield flask_app
        db.session.remove()
        db.drop_all()

@pytest.fixture(scope='function')
def db_session(app):
    """Fornece uma sessão isolada do banco para cada teste."""
    from db.database import db
    with app.app_context():
        yield db.session
        db.session.rollback() # Limpa as mudanças após o teste

# ==========================================
# UTILITÁRIO PARA DUMP JSON
# ==========================================

def json_serial(obj):
    """Serializador para converter datetime para string ISO no JSON."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError("Tipo não serializável")

# ==========================================
# TESTES DE CRUD
# ==========================================

def test_create_book_with_dump(db_session):
    """Testa a inserção (Create) de um novo livro e imprime dump."""
    from model.book import Book
    
    new_book = Book(
        title="O Senhor dos Anéis",
        author="J.R.R. Tolkien",
        isbn="9780007136599",
        publication_year=1954
    )
    db_session.add(new_book)
    db_session.commit()

    # Comentário: to_dict() converte o objeto ORM em um dicionário simples, 
    # ideal para APIs e serialização JSON.
    dump = json.dumps(new_book.to_dict(), indent=4, default=json_serial)
    print(f"\n--- DUMP CREATE ---\n{dump}")
    
    assert new_book.id is not None

def test_read_book_and_to_dict(db_session):
    """Testa a leitura e serialização to_dict()."""
    from model.book import Book
    
    book = Book(title="1984", author="George Orwell", isbn="9780451524935", publication_year=1949)
    db_session.add(book)
    db_session.commit()

    fetched_book = db_session.query(Book).filter_by(isbn="9780451524935").first()
    
    # Comentário: O dump abaixo mostra como os campos 'created_at' e outros 
    # aparecem após a persistência no banco.
    book_dict = fetched_book.to_dict()
    print(f"\n--- DUMP READ ---\n{json.dumps(book_dict, indent=4, default=json_serial)}")
    
    assert book_dict['title'] == "1984"

def test_update_book(db_session):
    """Testa atualização de campos."""
    from model.book import Book
    
    book = Book(title="Duna", author="Frank Herbert", isbn="9780441172719", publication_year=1965)
    db_session.add(book)
    db_session.commit()

    book.available = False
    book.genre = "Ficção Científica"
    db_session.commit()

    # Comentário: Verificamos o dump atualizado para garantir que os campos mudaram.
    print(f"\n--- DUMP UPDATE ---\n{json.dumps(book.to_dict(), indent=4, default=json_serial)}")
    
    assert book.available is False

def test_delete_and_move_to_trash(db_session):
    """Testa exclusão e movimentação para a tabela de lixeira."""
    from model.book import Book, BookTrash
    
    book = Book(title="Fundação", author="Isaac Asimov", isbn="9780553293357", publication_year=1951)
    db_session.add(book)
    db_session.commit()

    trashed = BookTrash(title=book.title, author=book.author, isbn=book.isbn, publication_year=book.publication_year)
    db_session.add(trashed)
    db_session.delete(book)
    db_session.commit()

    # Comentário: BookTrash contém o campo 'trashed_at', validando a diferença entre tabelas.
    print(f"\n--- DUMP TRASH ---\n{json.dumps(trashed.to_dict(), indent=4, default=json_serial)}")
    
    assert trashed.id is not None

def test_unique_isbn_constraint(db_session):
    """Testa se a restrição unique=True no ISBN funciona."""
    from model.book import Book
    
    # Usando ISBNs diferentes para evitar colisões entre testes
    book1 = Book(title="L1", author="A1", isbn="1111111111111", publication_year=2024)
    db_session.add(book1)
    db_session.commit()

    book2 = Book(title="L2", author="A2", isbn="1111111111111", publication_year=2024)
    db_session.add(book2)
    
    with pytest.raises(IntegrityError):
        db_session.commit()