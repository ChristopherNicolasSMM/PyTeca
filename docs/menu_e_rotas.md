# Menu e Rotas no Pyteca

O Pyteca utiliza um sistema de **menu lateral dinâmico** que consolida itens de três fontes, respeitando uma ordem de precedência clara. Além disso, todos os **blueprints** (rotas) são registrados automaticamente, sem necessidade de manutenção manual em `main.py`.

---

## 🧭 Menu Dinâmico

O menu é construído pela função `get_full_menu()` no módulo `utils/generate_model/menu_builder.py`. As fontes são consultadas na seguinte ordem:

1. **Itens manuais** registrados via decorador `@menu_item` (maior precedência).
2. **Itens do arquivo YAML complementar** (`templates/menu_complementar.yaml`).
3. **Itens gerados automaticamente** a partir dos modelos anotados (menor precedência).

### 1. Itens Manuais (Decorator `@menu_item`)

Você pode adicionar qualquer rota ao menu aplicando o decorador `@menu_item` diretamente na função da view (dentro de um blueprint). Exemplo:

```python
from utils.generate_model.menu_builder import menu_item

@web_bp.route("/dashboard")
@login_required
@menu_item("Dashboard", icon="bi-speedometer2", endpoint="web.dashboard")
def dashboard():
    return render_template("core/dashboard.html")
```

Parâmetros:

- `name`: nome exibido no menu.
- `icon`: classe do ícone (Bootstrap Icons, ex: `bi-book`).
- `endpoint`: nome do endpoint Flask (obrigatório para blueprints; para funções sem blueprint pode ser omitido).
- `parent`: endpoint ou `name` do item pai (para criar submenus).
- `clickable_parent`: se `True` e o item tiver filhos, o link do pai será clicável (além do toggle).

### 2. Arquivo YAML Complementar (`templates/menu_complementar.yaml`)

Permite definir ou sobrescrever itens de forma declarativa, sem mexer em código Python. Exemplo:

```yaml
items:
  - name: "Administração"
    endpoint: "#"
    icon: "bi-shield"
    clickable_parent: true
    children:
      - name: "Configurações"
        endpoint: "web.config"
        icon: "bi-gear"
      - name: "Usuários"
        endpoint: "admin.users"
        icon: "bi-people"
  - name: "Biblioteca"
    endpoint: "biblioteca.dashboard"
    icon: "bi-book"
    clickable_parent: true
    children:
      - name: "Livros"
        endpoint: "books.list"
        icon: "bi-grid"
      - name: "Autores"
        endpoint: "authors.list"
        icon: "bi-grid"
```

**Regras**:
- Se um item com o mesmo `endpoint` já existir nas fontes anteriores (manual), o YAML **não o substitui** (a precedência é manual > YAML).
- Para remover um item automático, defina-o no YAML com `hidden: true` (ainda não implementado, mas planejado) ou simplesmente não o inclua; ele será ignorado se o YAML fornecer uma versão alternativa? **Não**: itens automáticos só são adicionados se não forem conflitantes. Como a ordem de inserção é manual → YAML → automático, o automático será adicionado somente se o endpoint não tiver sido inserido antes. Portanto, para evitar um item automático, basta defini-lo manualmente ou no YAML.

### 3. Itens Gerados Automaticamente a partir dos Modelos

Quando um modelo SQLAlchemy utiliza as anotações `@label` e `@plural`, o `menu_builder` gera automaticamente um item de menu com:

- `name`: valor de `@label`
- `endpoint`: `{plural}.list`
- `icon`: padrão `bi-grid`, ou pode ser sobrescrito com `@menu_icon`

Exemplo no modelo:

```python
@label("Autores")
@plural("authors")
@menu_icon("bi-people")
class Author(db.Model):
    ...
```

Isso geraria um item `Autores` apontando para `authors.list`. Se desejar que este item apareça dentro de um submenu (ex.: "Biblioteca"), você pode usar `@menu_parent("Biblioteca")`:

```python
@menu_parent("Biblioteca")
class Author(db.Model):
    ...
```

O sistema, ao construir a árvore, agrupará os itens por `parent`.

### Construção da Árvore e Resolução de Conflitos

A função `build_tree(items)`:
- Remove duplicatas baseado no `endpoint` (a primeira ocorrência vence – portanto, manual e YAML têm precedência sobre automático).
- Constrói hierarquia usando os campos `parent` (pode referenciar `endpoint` ou `name` do pai).
- Ordena cada nível por `order` (se existir) e, depois, por `name`.

---

## 🌐 Rotas e Blueprints

### Auto‑descoberta de Blueprints

No `main.py`, a função `discover_and_register_blueprints` percorre recursivamente os pacotes `controller` e `api.routes`, importa cada módulo e registra todos os objetos `Blueprint` encontrados.

**Regras**:
- O blueprint deve ser uma instância de `flask.Blueprint` criada no módulo.
- O nome do blueprint não importa para o registro, mas é usado para `url_for`.
- Módulos de cache (`__pycache__`) e testes são ignorados.

Isso elimina a necessidade de registrar manualmente cada blueprint em `create_app`.

### Estrutura de Rotas Geradas pelo CRUD Generator

Para cada modelo anotado (ex.: `Author`), o gerador produz:

#### Rotas Web (HTML) – no controller (`controller/bookstore/author.py`)

| Método | Rota                         | Função                               | Descrição                                 |
|--------|------------------------------|--------------------------------------|-------------------------------------------|
| GET    | `/authors/`                  | `list()`                             | Listagem com SmartList, filtros, tabs (active/draft/trash) |
| GET    | `/authors/<int:item_id>`     | `detail(item_id)`                    | Página de detalhe                         |
| POST   | `/authors/<int:author_id>/trash`   | `trash(author_id)`             | Move para lixeira                         |
| POST   | `/authors/<int:author_id>/restore` | `restore(author_id)`           | Restaura da lixeira                       |
| POST   | `/authors/<int:author_id>/delete`  | `delete_permanent(author_id)`  | Exclusão definitiva (só admin)           |
| POST   | `/authors/<int:author_id>/discard` | `discard_draft(author_id)`     | Descarta rascunho                         |

#### Rotas API (JSON) – em `api/routes/bookstore/author_routes.py`

| Método   | Rota                                       | Descrição                                   |
|----------|--------------------------------------------|---------------------------------------------|
| GET      | `/api/bookstore/authors/`                  | Listagem paginada (parâmetros: status, search, sort, dir, page, per_page) |
| GET      | `/api/bookstore/authors/<int:id>`          | Obtém um item                               |
| POST     | `/api/bookstore/authors/draft`             | Cria um rascunho vazio                      |
| PATCH    | `/api/bookstore/authors/<int:id>/autosave` | Auto-salva rascunho                         |
| POST     | `/api/bookstore/authors/<int:id>/publish`  | Publica rascunho                            |
| POST     | `/api/bookstore/authors/`                  | Cria direto (status active)                 |
| PUT/PATCH| `/api/bookstore/authors/<int:id>`          | Atualiza                                    |
| POST     | `/api/bookstore/authors/<int:id>/trash`    | Move para lixeira                           |
| POST     | `/api/bookstore/authors/<int:id>/restore`  | Restaura                                    |
| DELETE   | `/api/bookstore/authors/<int:id>`          | Exclui permanentemente (admin)              |
| DELETE   | `/api/bookstore/authors/<int:id>/discard`  | Descarta rascunho                           |

#### Rotas de Opções (para relacionamentos)

Para campos do tipo `ForeignKey`, o sistema fornece um endpoint de busca:

- `GET /api/options/<table_name>?search=termo&page=1`
  Retorna `{ results: [{id, text}], pagination: {more: bool} }`
  (implementado em `api/routes/core/options_routes.py`)

Esse endpoint é usado pelos modais de formulário para preencher selects com autocomplete.

### Rotas Principais do Core (não geradas)

| Rota                         | Blueprint    | Função                         | Descrição                          |
|------------------------------|--------------|--------------------------------|------------------------------------|
| `/`                          | `web`        | `index()`                      | Redireciona para dashboard ou login|
| `/login`                     | `web`        | `login()`                      | Página de login                    |
| `/register`                  | `web`        | `register()`                   | Página de solicitação de registro  |
| `/dashboard`                 | `web`        | `dashboard()`                  | Dashboard (placeholder)            |
| `/profile`                   | `web`        | `profile()`                    | Perfil do usuário                   |
| `/atualizar_perfil`          | `web`        | `atualizar_perfil()`           | POST para editar perfil             |
| `/alterar_senha`             | `web`        | `alterar_senha()`              | POST para alterar senha             |
| `/notifications`             | `web`        | `notifications()`              | Página de notificações              |
| `/api/notifications`         | `api`        | várias                         | CRUD de notificações (JSON)         |
| `/api/layout/save`           | `smart_list_api` | `save_layout()`            | Salva layout da SmartList           |
| `/api/layout/<list_id>/reset`| `smart_list_api` | `reset_layout()`           | Reseta layout                       |
| `/api/auth/update_theme`     | `api_auth`   | `update_theme()`               | Alterna tema claro/escuro (JSON)    |

---

## 🧪 Testando Rotas e Menu

### Verificar rotas registradas

```bash
flask routes
```

### Forçar recarga de blueprints (em desenvolvimento)

O Flask em modo debug já recarrega o aplicativo quando arquivos são alterados. Se você adicionar um novo blueprint dentro de `controller/` ou `api/routes/`, ele será detectado e registrado na próxima requisição (desde que o módulo seja importado – o que já ocorre via `pkgutil.walk_packages`). Em produção, é necessário reiniciar o servidor.

### Customização do Menu

1. **Para adicionar um item manualmente**: use `@menu_item` na view desejada.
2. **Para agrupar itens automáticos**: adicione `@menu_parent("Nome do Grupo")` no modelo.
3. **Para sobrescrever um item automático**: crie um item com o mesmo `endpoint` em `menu_complementar.yaml` ou via `@menu_item`. Como a precedência é manual > YAML > automático, o automático será ignorado.
4. **Para remover um item automático sem criar outro**: não há suporte direto ainda. Uma solução é definir o item no YAML com `hidden: true` (funcionalidade a ser implementada) ou definir um item manual com o mesmo endpoint mas com `endpoint: "#"` e `visible: false`.

---

## 📌 Considerações Finais

- O sistema de menu é **totalmente configurável** sem reinicialização (arquivos YAML são lidos a cada requisição).
- A auto-descoberta de blueprints torna a adição de novos módulos **plug-and-play**.
- O gerador de CRUD produz rotas consistentes, seguindo o padrão RESTful e boas práticas de segurança (login_required, admin apenas para ações destrutivas).

Para mais detalhes sobre a criação de novos modelos e geração de CRUD, consulte o `README.md`.
