# 08 — Model Builder: Filtros na Lista e Seleção Completa de FK

## Parte 1 — Filtros e agrupamento na lista de Modelos Criados

A lista "Modelos Criados via Builder" ganhou:

- **Busca por texto** (nome do model ou nome da tabela), com debounce de 300ms
- **Filtro por módulo**, populado via `SELECT DISTINCT module` real
  (`GET /api/core/builder/model/modules`) — sempre reflete os módulos que
  de fato existem nas definições salvas, nunca uma lista hardcoded
- **Agrupamento por módulo** (toggle), que troca a renderização da tabela
  para seções com cabeçalho de grupo e contagem

### API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/core/builder/model/?search=X&module=Y&group_by=module` | Lista filtrada/agrupada |
| `GET` | `/api/core/builder/model/modules` | `SELECT DISTINCT module` |

Sem `group_by`, a resposta é `{"models": [...]}` (formato anterior,
compatível). Com `group_by=module`, vira `{"groups": [{"module": "...", "models": [...]}]}`.

---

## Parte 2 — Seleção real de tabela, coluna-alvo e campo de exibição em FK

### O problema original

A chave estrangeira sempre referencia uma coluna específica da tabela
destino — em SQL, essa coluna **precisa** ser chave primária ou ter
constraint `UNIQUE` (exigência do próprio padrão SQL, idêntica em SQLite e
PostgreSQL). Até esta correção, o Model Builder:

- Pedia o nome da tabela em **texto livre**, sem validar se existia
- Sempre assumia a **PK (`id`)** como alvo da FK, sem permitir escolher
  uma chave alternativa (ex: CPF com `unique=True`)
- Assumia `display_field="name"` hardcoded, quebrando em runtime para
  qualquer tabela que usasse outro nome de coluna de texto

### A correção

**`schema_inspector.py`** — introspecção real via `sqlalchemy.inspect`,
retornando para qualquer tabela:

- `fk_target_candidates`: colunas que são PK **ou** têm constraint UNIQUE
  (incluindo índices únicos, que é como SQLite frequentemente expõe isso)
- `display_field_candidates`: colunas de texto sugeridas para exibição,
  com as mais prováveis (`name`, `nome`, `titulo`, `descricao`...) primeiro

### UI — três selects encadeados

```
Tabela referenciada:    [▼ pessoas (3 colunas)]
                                │
                                ▼ dispara fetch de GET /tables/pessoas
Coluna-alvo da FK:      [▼ id (chave primária)]     ← SÓ 1 candidata = desabilitado
                         [  cpf (único)]              ← 2+ candidatas = habilitado, com dica visual
Campo de exibição:      [▼ nome]                     ← sugerido, mas trocável
```

**Auto-disable**: quando a tabela só tem uma coluna válida como alvo (o
caso comum — só o `id`), o select de coluna-alvo fica desabilitado e
pré-selecionado, sem decisão pendente para o usuário. Quando há mais de
uma candidata (ex: `pessoas` com `id` + `cpf` único), o select habilita e
mostra um badge "N opções" como indicação visual.

### Tipo Python inferido automaticamente

Quando a FK aponta para uma coluna que não é a PK inteira (ex: `cpf`,
`VARCHAR`), o campo gerado no model é tipado corretamente como `str`, não
`int`:

```python
# FK normal (aponta para id, Integer)
categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"), nullable=False)

# FK por chave alternativa (aponta para cpf, VARCHAR — unique=True)
cliente_id: Mapped[str] = mapped_column(ForeignKey("pessoas.cpf"), nullable=False)
cliente: Mapped["Pessoa"] = relationship()  # funciona nativamente, sem primaryjoin manual
```

O `relationship()` funciona sem nenhuma configuração extra — o SQLAlchemy
infere a junção a partir da própria declaração de `ForeignKey()`,
confirmado com teste funcional usando SQLite real.

### Validação em duas camadas

- **Client-side**: bloqueia preview/criação se qualquer FK estiver sem
  tabela, coluna-alvo ou campo de exibição definidos
- **Server-side** (`validate_definition`): revalida contra o schema real —
  confirma que a tabela existe, que a coluna-alvo é de fato PK ou UNIQUE,
  e que o campo de exibição existe na tabela

### Resolução do nome da classe Python (`fk_class`)

Bônus relacionado, mesma área de código: prioriza o nome real da classe
via `db.Model.registry` quando a tabela já tem um model Python mapeado
(sempre correto), com heurística snake_case → PascalCase como fallback
para tabelas sem model ainda.

---

## Decisão registrada: chave primária composta fica para uma v2.0 futura

Foi discutido o caso de tabelas de detalhe/associação com chave composta
(ex: `pedido_itens` com PK `(pedido_id, item_id)`). SQLAlchemy suporta
nativamente, mas isso é uma mudança de modelagem da tabela em si — não
relacionada à seleção de FK que esta entrega resolve — e tem efeito
cascata em praticamente todo o CrudGen (`service.get_by_id()`, rotas
`/<int:id>`, SmartList, exportação, hooks — tudo hoje assume PK simples
inteira).

**Decisão**: registrado como item de backlog separado (v2.0), não
implementado nesta entrega. O caso de "chave alternativa única" (CPF)
resolve a maior parte dos casos reais sem precisar dessa complexidade.

## Antes vs Depois

| | Antes | Depois |
|---|---|---|
| Lista de models | Sem filtro nenhum | Busca + filtro por módulo (select distinct) + agrupamento |
| Tabela referenciada | Texto livre, sem validação | Select com tabelas reais do banco |
| Coluna-alvo da FK | Sempre `id`, sem escolha | Select com PK + UNIQUE; auto-disable quando só há 1 opção |
| Campo de exibição | Hardcoded `"name"` | Select com colunas reais, sugestão visível, trocável |
| Chave alternativa (CPF) | Não suportado | Suportado nativamente via `unique=True` já existente + introspecção |
| Nome da classe FK | Heurística frágil em nomes compostos | Prioriza model real registrado; heurística melhorada como fallback |
| PK composta | — | Backlog v2.0, não implementado |
