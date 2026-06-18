# Fix 21 — Hooks pbo_/pai_ + Menu YAML com requires_permission

## Parte 1 — Ajuste nos Hooks (fix20 corrigido)

### Renomeação: pre_ → pbo_ e post_ → pai_

- **pbo_** = Processo Antes da Operação
- **pai_** = Processo Após a Integração

Todos os hooks agora recebem também o **objeto trafegado** como argumento.

### Assinaturas por camada (stub gerado para cada model)

**Controller (`book_hooks.py`)**:
```python
def pbo_list(request)                         # interceptar listagem HTML
def pai_list(response, request)               # substituir response
def pbo_delete(item_id, action, obj)          # obj = registro ORM antes de apagar
def pai_delete(item_id, action, obj, result)  # obj pode ser None após delete permanente
```

**Service (`book_service_hooks.py`)**:
```python
def pbo_apply_fields(obj, data)   # retorne data modificado ou None
def pai_apply_fields(obj, data)   # obj já mutado, antes do commit
```

**Routes/API (`book_routes_hooks.py`)**:
```python
def pbo_list(request)
def pai_list(payload, request)               # payload = dict JSON
def pbo_create(data, request)                # retorne data modificado ou None
def pai_create(obj, request)                 # obj = novo registro ORM
def pbo_update(item_id, data, request)       # retorne data modificado ou None
def pai_update(obj, request)                 # obj = registro atualizado
def pbo_delete(item_id, action, request)     # action: "trash" | "delete_permanent"
def pai_delete(item_id, action, result, request)
```

### Como aplicar os hooks (parte 1)

```bash
# Regenerar os models existentes para criar os _hooks.py
python main.py generate --model model/bookstore/author.py --overwrite
python main.py generate --model model/bookstore/book.py   --overwrite
python main.py generate --model model/bookstore/loan.py   --overwrite

# Log esperado para cada model:
#   🪝 Hooks criados: controller/bookstore/book_hooks.py
#   🪝 Hooks criados: services/bookstore/book_service_hooks.py
#   🪝 Hooks criados: api/routes/bookstore/book_routes_hooks.py
```

---

## Parte 2 — Menu YAML com `requires_permission`

### Como funciona

Qualquer item em `menu_complementar.yaml` pode declarar:

```yaml
- name: "Usuários e Papéis"
  endpoint: "admin_roles.index"
  icon: "bi-shield-lock"
  parent: "Administração"
  requires_permission: "admin"
```

O context processor `inject_dynamic_menu` agora filtra os itens chamando
`filter_menu_by_permission(menu_items, current_user)` — itens com
`requires_permission` que o usuário não possui são removidos do menu
antes de renderizar.

- Itens **sem** `requires_permission` aparecem para qualquer usuário autenticado
- `is_admin=True` passa em qualquer cheque (mesmo comportamento do `has_permission`)
- A filtragem é recursiva — filhos de um grupo protegido também são filtrados

### O que mudou no menu_complementar.yaml

- Todos os itens de Administração ganharam `requires_permission: "admin"`
- Item "Usuários e Papéis" foi **descomentado** e ativado com o endpoint
  correto `admin_roles.index` (criado no fix18)

### Arquivos modificados (parte 2)

- `utils/generate_model/menu_builder.py` — nova função `filter_menu_by_permission()`
- `main.py` — context processor agora aplica o filtro
- `templates/menu_complementar.yaml` — `requires_permission` adicionado +
  item Usuários e Papéis ativado

---

## Validações feitas antes da entrega

- Sintaxe Python de todos os arquivos
- Compilação dos 3 templates `.j2` com os hooks renomeados (zero pre_/post_ restantes)
- Teste funcional do filtro de menu com SQLite simulado: admin vê tudo,
  librarian vê só itens sem requires_permission, itens sem requires_permission
  aparecem para todos os autenticados

## O que ainda falta (próximo item)

- CLI `--skip-html` / `--only=` (regeneração parcial, complementar aos hooks)
- Console Python em runtime (pendente decisão de escopo de segurança)
- Documentação consolidada dos manuais 01-03 (arquitetura, gerador, SmartList)
