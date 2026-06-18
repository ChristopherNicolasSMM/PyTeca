# 02 — Gerador de Código (CrudGen)

## Visão geral

O gerador transforma um arquivo de model Python anotado em um CRUD completo.
Um único comando cria controller, service, rotas de API e todos os templates HTML.

```
Model + Anotações → generate_from_model.py → Controller + Service + Routes + Templates
```

## Uso

```bash
# Gerar (primeira vez — não sobrescreve se já existir)
python main.py generate --model model/bookstore/book.py

# Regenerar após mudar o model ou corrigir um .j2
python main.py generate --model model/bookstore/book.py --overwrite

# Gerar só alguns artefatos (não toca nos outros)
python main.py generate --model model/bookstore/book.py --overwrite --only=service,routes
python main.py generate --model model/bookstore/book.py --overwrite --skip=html
python main.py generate --model model/bookstore/book.py --overwrite --skip=controller
```

### Flags do CLI

| Flag | Descrição |
|---|---|
| `--model / -m` | Caminho do model (obrigatório) |
| `--overwrite / -o` | Sobrescreve arquivos já existentes |
| `--theme / -t` | Pasta de templates alternativos (padrão: `standard`) |
| `--only` | Gera só os artefatos listados: `controller`, `service`, `routes`, `templates` |
| `--skip` | Pula os artefatos listados. Aceita `html` como alias para `templates` |
| `--add-to-root-menu` | Adiciona entry no `menu_complementar.yaml` automaticamente |

`--only` tem prioridade sobre `--skip` se ambos forem informados.

## O que é gerado

| Artefato | Template usado | Destino |
|---|---|---|
| Controller HTML | `controller.py.j2` | `controller/{subdir}/{model}.py` |
| Service | `service.py.j2` | `services/{subdir}/{model}_service.py` |
| Rotas de API | `routes.py.j2` | `api/routes/{subdir}/{model}_routes.py` |
| Manage HTML | `manage.html.j2` | `templates/{subdir}/{plural}/manage.html` |
| Detail HTML | `detail.html.j2` | `templates/{subdir}/{plural}/detail.html` |
| Modal de Form | `form_modal.html.j2` | `templates/{subdir}/{plural}/_modals/{model}_form_modal.html` |
| Model Python | `model.py.j2` | `model/{subdir}/{model}.py` (só via Model Builder UI) |

Os arquivos `_hooks.py` (controller, service, routes) são criados ao lado
de cada arquivo gerado — uma única vez, nunca sobrescritos.

## Anotações disponíveis

```python
from annotations import (
    label,          # @label("Livros") — nome singular para UI
    plural,         # @plural("books") — endpoints e URLs
    listview,       # @listview(columns=[...], filters=[...])
    Column,         # ColumnDef dentro do @listview
    Filter,         # FilterDef dentro do @listview (texto)
    form,           # @form(fields=[...], groups=[...])
    Group,          # Grupo de campos dentro do @form
    required,       # @required("campo", "Mensagem")
    max_length,     # @max_length("campo", 100)
    display_field,  # @display_field("nome") — campo exibido em FK dropdown
    choices,        # @choices("genre", label="Gênero") — SELECT DISTINCT no filtro
    permission,     # @permission("acao", role_required="papel") — Camada 2 de RBAC
)
```

### `@choices` — filtro dinâmico com SELECT DISTINCT

```python
@choices("genre",    label="Gênero")
@choices("language", label="Idioma")
class Book(db.Model):
    genre: Mapped[str] = mapped_column(String(60))
```

O filtro é populado automaticamente com os valores distintos que existem no
banco — atualiza conforme os dados mudam, sem precisar editar o código.

Campos marcados com `@choices` são **removidos dos filtros estáticos** do
`@listview` (o gerador faz essa deduplicação na fonte para evitar que o
mesmo campo apareça duas vezes na tela).

## Checklist de novo model

```
[ ] Arquivo em model/{subdir}/{nome}.py
[ ] Status Enum: class {Model}Status(str, PyEnum) com DRAFT, ACTIVE, TRASH
[ ] @label, @plural, @listview (columns + filters), @form (fields + groups)
[ ] @display_field("campo")       — obrigatório para FK dropdown funcionar
[ ] @required para cada obrigatório
[ ] @choices para filtros com SELECT DISTINCT (opcional)
[ ] cascade="all, delete-orphan" em relacionamentos filhos
[ ] @property planas para FK usadas em listagem (ex: author_name)
[ ] to_dict() incluindo status.value e {rel}_name para cada FK
[ ] python main.py generate --model model/{subdir}/{nome}.py
[ ] Testar CRUD completo (criar, editar, lixeira, restaurar, excluir)
```

## Como os `.j2` funcionam

Os arquivos `.j2` são **templates de templates**. Eles contêm variáveis Jinja2
(`{{ class_name }}`, `{{ plural }}`, etc.) que o gerador substitui por valores
derivados das anotações do model, produzindo um arquivo Python ou HTML final.

```
service.py.j2               →  book_service.py
────────────────────────────────────────────────
class {{ class_name }}Service:     →  class BookService:
    def list(self, ...):           →      def list(self, ...):
        {{ class_name }}.query     →          Book.query
```

### Variáveis disponíveis nos `.j2`

| Variável | Exemplo | Origem |
|---|---|---|
| `{{ class_name }}` | `Book` | Nome da classe Python |
| `{{ class_name_lower }}` | `book` | Lowercase |
| `{{ label }}` | `Livros` | `@label` |
| `{{ plural }}` | `books` | `@plural` |
| `{{ output_subdir }}` | `bookstore` | Subpasta do model |
| `{{ module_name }}` | `book` | Nome do arquivo sem extensão |
| `{{ columns }}` | `ColumnDef(...),...` | `@listview(columns=...)` processado |
| `{{ filters }}` | `FilterDef(...),...` | `@listview(filters=...)` processado (sem @choices) |
| `{{ default_sort }}` | `title` | `@listview(default_sort=...)` |
| `{{ search_block }}` | código Python | Bloco de busca gerado |

## `_build_columns_block` — resolução automática de FK

Uma função crítica no gerador: ao encontrar uma coluna cujo nome referencia
um relacionamento SQLAlchemy, resolve automaticamente para a `@property`
plana correspondente, sem exigir edição manual do model:

- `Column("author", ...)` → `ColumnDef("author_name", ...)` (nome de relacionamento)
- `Column("user.username", ...)` → `ColumnDef("user_username", ...)` (chave com ponto)

Ambos os casos definem `sortable=False` automaticamente (relacionamentos nunca
são ordernáveis diretamente pelo banco sem join).

## Erros comuns

| Sintoma | Causa | Fix |
|---|---|---|
| `BookStatus.ACTIVE` na célula | Enum sem `.value` | Filtro `\|smart_val` no template |
| `<Author ...>` na célula | `ColumnDef("author", ...)` resolveu mas `@property author_name` falta | Adicionar `@property` plana no model |
| `CHOICES_FILTERS is not defined` | `@choices` criou variável de módulo que exige app context | Fix13: a variável foi movida para dentro de `list()` |
| Filtro duplicado na tela | `Filter("genre", ...)` no `@listview` + `@choices("genre")` | `_build_filters_block` já remove — regenere com `--overwrite` |
