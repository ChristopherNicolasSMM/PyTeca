# PyTeca — Skill de Projeto

## Quando usar esta skill
Use antes de qualquer tarefa que envolva o projeto PyTeca:
- Criar ou editar modelos, services, controllers, routes, templates
- Corrigir bugs no projeto
- Gerar código com `generate_from_model.py`
- Trabalhar com SmartList, SmartListConfig, ColumnDef
- Qualquer arquivo em `src/` do repositório github.com/ChristopherNicolasSMM/PyTeca

---

## Stack e ambiente

- **Backend**: Flask, SQLAlchemy (Mapped/mapped_column), Flask-Login, Flask-CORS, SQLite (dev)
- **Frontend**: Bootstrap 5, Nice Admin legacy theme, Jinja2, Vanilla JS
- **Ambiente**: Windows, venv, Python 3.10+
- **Repo**: https://github.com/ChristopherNicolasSMM/PyTeca
- **Entrypoint**: `src/main.py` — `python main.py` ou `python main.py generate --model <path>`

---

## Arquitetura de pastas

```
src/
├── annotations/          # Decorators @label, @plural, @listview, @form, @required, etc.
├── api/routes/
│   ├── bookstore/        # book_routes.py, author_routes.py, loan_routes.py
│   └── core/             # notifications_routes.py, options_routes.py, etc.
├── controller/
│   ├── bookstore/        # book.py, author.py, loan.py  ← GERADOS pelo .j2
│   └── core/
├── model/
│   ├── bookstore/        # book.py, author.py, loan.py
│   └── core/
├── services/
│   ├── bookstore/        # book_service.py, etc.  ← GERADOS pelo .j2
│   └── core/
├── templates/
│   ├── _components/      # smart_list.html, fk_selector_modal.html
│   ├── bookstore/
│   │   └── books/        # manage.html, detail.html, _modals/book_form_modal.html
│   └── core/
├── utils/
│   ├── generate_from_model.py   # CLI gerador
│   ├── smart_list/              # config.py, renderer.py, export.py
│   └── generate_model/
│       └── templates/standard/  # .j2 templates para geração
└── static/css/           # style.css, style_dark.css, themes.css, smart_list.css
```

**Regra de ouro**: Controllers, Services e Templates HTML gerados NUNCA devem ser editados diretamente. Corrija sempre nos `.j2` e regenere.

---

## Convenções de nomenclatura

| Elemento | Padrão | Exemplo |
|---|---|---|
| Pasta de módulo | nome do model | `controller/bookstore/book.py` |
| Blueprint | `{plural}_bp` | `books_bp` |
| Service | `{ClassName}Service` | `BookService` |
| Rota API | `/api/{subdir}/{plural}/` | `/api/bookstore/books/` |
| Template | `{subdir}/{plural}/manage.html` | `bookstore/books/manage.html` |
| Modal | `_modals/{singular}_form_modal.html` | `_modals/book_form_modal.html` |

---

## Modelo padrão (anotações obrigatórias)

```python
from annotations import label, plural, listview, Column, Filter, form, Group, required, display_field

@label("Livros")
@plural("books")
@listview(columns=[...], filters=[...])
@form(fields=[...], groups=[...])
@display_field("title")          # OBRIGATÓRIO para FK dropdown funcionar
@required("title", "mensagem")
class Book(db.Model):
    __tablename__ = "books"
    status: Mapped[str] = mapped_column(Enum(BookStatus), default=BookStatus.DRAFT, nullable=False)
```

**Status padrão**: todo model tem `{Model}Status(str, PyEnum)` com `DRAFT`, `ACTIVE`, `TRASH`.

---

## SmartList — padrão de ColumnDef

```python
# NUNCA use chaves com ponto (user.username) — Jinja2 attr não resolve
# SEMPRE use @property plana no modelo
ColumnDef("author_name",   "Autor",   sortable=False)  # @property no model
ColumnDef("user_username", "Usuário", sortable=False)  # @property no model
ColumnDef("book_title",    "Livro",   sortable=False)  # @property no model

# Ordenação só por colunas diretas (não relacionamentos)
# O service.py.j2 já tem _SORTABLE whitelist — nunca sort em FK
```

**Propriedades planas obrigatórias** em models com FK na SmartList:
```python
@property
def author_name(self) -> str:
    return self.author.name if self.author else "—"
```

---

## Service — padrões críticos

```python
# _apply_fields: sempre converter tipos
# - campos _id     → int()
# - campos Integer → int() (year, quantity, available, etc.)
# - campos Date/DateTime → _parse_date() — aceita dd/mm/yyyy, yyyy-mm-dd, ISO

# create() e update(): sempre try/except + rollback
try:
    db.session.commit()
except Exception as e:
    db.session.rollback()
    return ServiceResult(success=False, error=_friendly_db_error(e), code=422)

# delete_permanent(): idem — cascade pode gerar IntegrityError
```

---

## Templates — armadilhas conhecidas

| Armadilha | Causa | Fix |
|---|---|---|
| `<built-in method title of str>` | `{{ class_name_lower.title }}` no j2 | Usar `{{ label }}` |
| `bookss` no breadcrumb | `{{ plural }}s` duplica o s | Usar `{{ label }}s` |
| `BookStatus.ACTIVE` na célula | `Enum` sem `.value` | Filtro `\|smart_val` |
| `<Author ...>` na célula | `row\|attr("author")` retorna objeto ORM | Usar `author_name` @property |
| Chaves com ponto em ColumnDef | `row\|attr("user.username")` falha | Usar @property plana |
| `'>' not supported str and int` | `available > 0` sem cast | `int(self.available or 0)` |

---

## Filtro Jinja global: `smart_val`

Registrado em `main.py`. Usar em qualquer template:
```jinja
{{ book.status|smart_val }}     {# 'active' em vez de 'BookStatus.ACTIVE' #}
{{ loan.user|smart_val }}       {# nome em vez de '<User ...>' #}
{{ item.created_at|smart_val }} {# '16/06/2026 14:30' #}
{{ None|smart_val }}            {# '—' #}
```

---

## FK Dropdown (modal)

```html
<!-- Estrutura obrigatória para o JS funcionar -->
<div class="fk-field" data-field="author_id" data-foreign-table="authors">
  <input type="hidden" name="author_id" class="fk-hidden-id">
  <input type="text" class="fk-search-input" placeholder="Clique ou digite...">
  <ul class="fk-dropdown list-group position-absolute w-100 shadow"
      style="z-index:9999;display:none;top:100%;left:0;"></ul>
</div>
```

- Carrega ao focar (sem digitação)
- Filtra ao digitar com debounce 280ms
- Endpoint: `/api/options/{foreign_table}?search=...`
- O model precisa ter `@display_field("name")` para a opção exibir o nome

---

## Geração de código

```bash
# Gerar todos os artefatos para um model
python main.py generate --model model/bookstore/book.py

# Forçar sobrescrita (após fix nos .j2)
python main.py generate --model model/bookstore/book.py --overwrite

# Regenerar todos de uma vez
python main.py generate --model model/bookstore/book.py --overwrite
python main.py generate --model model/bookstore/loan.py --overwrite
python main.py generate --model model/bookstore/author.py --overwrite
```

**O que é gerado**:
- `controller/bookstore/book.py`
- `services/bookstore/book_service.py`
- `templates/bookstore/books/manage.html`
- `templates/bookstore/books/detail.html`
- `templates/bookstore/books/_modals/book_form_modal.html`

---

## Bugs já resolvidos (não repetir)

1. **`author_id` NOT NULL no draft** → Book não suporta draft; usar POST direto na criação
2. **Sort em relacionamento** → `_SORTABLE` whitelist no service evita `NotImplementedError`
3. **`loans.book_id` NOT NULL ao deletar Book** → `cascade="all, delete-orphan"` no relacionamento
4. **CSV encoding** → BOM UTF-8 (`\ufeff`) no início do arquivo
5. **Notificações 404** → `notifications_bp` precisava de `url_prefix="/api"`
6. **Status no dropdown** → `enum_fields = []` no controller antigo; use `_get_enum_fields()` gerado pelo controller.py.j2
7. **Datas como string no SQLite** → `_parse_date()` no `_apply_fields` do service
