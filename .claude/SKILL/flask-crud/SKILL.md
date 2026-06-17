# Flask CRUD — Skill Reutilizável

## Quando usar esta skill
Use em qualquer projeto Python/Flask com:
- Padrão MVC: model / service / controller / api routes
- SQLAlchemy com relacionamentos e status Enum
- Templates Jinja2 com formulários modais
- Exportação CSV/Excel/PDF de listagens

---

## Padrões de model SQLAlchemy

### Status Enum (padrão str para SQLite compatibilidade)
```python
from enum import Enum as PyEnum
from sqlalchemy import Enum

class BookStatus(str, PyEnum):
    DRAFT  = "draft"
    ACTIVE = "active"
    TRASH  = "trash"

class Book(db.Model):
    status: Mapped[str] = mapped_column(
        Enum(BookStatus), default=BookStatus.DRAFT, nullable=False
    )

    # to_dict: sempre retornar .value, nunca o Enum bruto
    def to_dict(self):
        return {
            "status": self.status.value if hasattr(self.status, "value") else self.status,
        }
```

### Relacionamentos com cascade seguro
```python
# Se B depende de A, e deletar A deve deletar B:
loans: Mapped[list["Loan"]] = relationship(
    back_populates="book",
    cascade="all, delete-orphan",
    passive_deletes=True,
)

# Se B deve ser preservado (apenas desassociar):
# NÃO use cascade — mas trate o IntegrityError no delete_permanent
```

### Propriedades planas para FK display
```python
# Sempre adicionar para cada FK usada em listagem
@property
def author_name(self) -> str:
    return self.author.name if self.author else "—"

@property
def is_available(self) -> bool:
    # Cast defensivo: o form pode enviar string
    try:
        return self.is_active and int(self.available or 0) > 0
    except (TypeError, ValueError):
        return False
```

---

## Padrões de Service

### _apply_fields robusto
```python
_DATE_FIELDS = set()  # detectado via mapper no boot
_READONLY    = {"id", "status", "created_at", "updated_at", "trashed_at"}

def _apply_fields(self, obj, data, strict=True):
    from sqlalchemy import Integer
    from sqlalchemy.orm import ColumnProperty

    _int_fields = {
        p.key for p in obj.__class__.__mapper__.iterate_properties
        if isinstance(p, ColumnProperty) and isinstance(p.columns[0].type, Integer)
    }

    for key, value in data.items():
        if key in _READONLY or not hasattr(obj, key):
            continue
        if key in _DATE_FIELDS:
            value = _parse_date(value)           # aceita dd/mm/yyyy, ISO, datetime
        if key.endswith("_id") or key in _int_fields:
            value = int(value) if value not in (None, "") else None
        setattr(obj, key, value)
    obj.updated_at = datetime.now(timezone.utc)
```

### Erros amigáveis
```python
def _friendly_db_error(exc):
    msg = str(exc)
    m = re.search(r"UNIQUE constraint failed:\s*\w+\.(\w+)", msg, re.I)
    if m: return f"Valor duplicado no campo '{m.group(1)}'."
    m = re.search(r"NOT NULL constraint failed:\s*\w+\.(\w+)", msg, re.I)
    if m:
        if "UPDATE" in msg.upper():
            return f"Não é possível excluir: outros registros dependem deste ('{m.group(1)}')."
        return f"Campo '{m.group(1)}' é obrigatório."
    if "FOREIGN KEY" in msg.upper():
        return "Referência inválida ou registros dependentes existem."
    return f"Erro: {msg.splitlines()[0][:200]}"
```

### create/update/delete sempre com try/except
```python
db.session.add(obj)
try:
    db.session.commit()
except Exception as e:
    db.session.rollback()
    logger.warning("Erro ao salvar %s: %s", cls.__name__, e)
    return ServiceResult(success=False, error=_friendly_db_error(e), code=422)
```

---

## Padrões de Controller Flask

### Enum fields: detecção automática (nunca hardcode `[]`)
```python
def _get_enum_fields(model_class, form_fields):
    from sqlalchemy import Enum as SAEnum
    from sqlalchemy.orm import ColumnProperty
    from enum import EnumMeta
    import inspect

    result = []
    module = inspect.getmodule(model_class)
    for field in form_fields:
        options = None
        attr = getattr(model_class, field, None)
        if attr and hasattr(attr, "type") and isinstance(attr.type, SAEnum):
            if getattr(attr.type, "enum_class", None):
                options = [(e.value, e.name.replace("_"," ").title())
                           for e in attr.type.enum_class]
        if options is None:
            for name, obj in vars(module).items():
                if isinstance(obj, EnumMeta) and field.replace("_","").lower() in name.lower():
                    options = [(e.value, e.name.replace("_"," ").title()) for e in obj]
                    break
        if options:
            result.append({"name": field, "options": options})
    return result
```

---

## Padrões de Template Jinja2

### Filtro global smart_val (registrar em create_app)
```python
from enum import Enum as _Enum
from datetime import datetime as _dt

@app.template_filter("smart_val")
def smart_val_filter(val):
    if val is None or val == "": return "—"
    if isinstance(val, _Enum): return str(val.value)
    if isinstance(val, _dt): return val.strftime("%d/%m/%Y %H:%M")
    raw = str(val)
    if raw.startswith("<") and raw.endswith(">"):
        return getattr(val, "name", getattr(val, "title", "—"))
    return raw or "—"
```

### FK Dropdown no modal
```html
<!-- data-foreign-table deve corresponder ao @plural do model relacionado -->
<div class="fk-field" data-field="author_id" data-foreign-table="authors">
  <input type="hidden" name="author_id" class="fk-hidden-id">
  <input type="text" class="fk-search-input" placeholder="Clique ou digite...">
  <ul class="fk-dropdown list-group position-absolute w-100 shadow"
      style="z-index:9999;display:none;top:100%;left:0;max-height:200px;overflow-y:auto;"></ul>
</div>
<!-- O endpoint /api/options/{table}?search=... retorna {results:[{id,text}]} -->
```

### Date input (sempre type=date, nunca text para datas)
```html
<input type="date" name="loan_date" class="form-control">
<!-- O service converte YYYY-MM-DD para datetime automaticamente -->
<!-- Ao carregar para edição: iso.substring(0,10) -->
```

### Validação client-side antes de enviar
```javascript
const REQUIRED = {{ required_fields | tojson }};
function validateForm(data) {
    const errors = [];
    REQUIRED.forEach(field => {
        if (!(data[field] ?? "").toString().trim()) {
            errors.push(`${field.replace(/_/g," ")} é obrigatório`);
            document.getElementById(field)?.classList.add("is-invalid");
        }
    });
    return errors;
}
```

---

## Checklist para novo model

```
[ ] Criar model com @label, @plural, @listview, @form, @display_field, @required
[ ] Status Enum (str, PyEnum) com DRAFT/ACTIVE/TRASH
[ ] @property plana para cada FK usada em listagem (ex: author_name)
[ ] cascade="all, delete-orphan" em relacionamentos filhos
[ ] to_dict() retornando status.value e _name para cada FK
[ ] Rodar generate --model ... --overwrite
[ ] Testar: criar, editar, mover para lixeira, restaurar, excluir permanente
[ ] Verificar sort na SmartList (só colunas diretas)
[ ] Verificar display de Enum na lista (não deve aparecer EnumName.VALUE)
```

---

## Armadilhas comuns em Flask/SQLAlchemy

| Problema | Causa | Fix |
|---|---|---|
| `NotImplementedError` no sort | `getattr(Model, "author")` retorna relationship | Whitelist `_SORTABLE` com colunas do mapper |
| `NOT NULL` ao deletar | SQLAlchemy faz UPDATE SET fk=NULL antes de DELETE | `cascade="all, delete-orphan"` ou tratar no service |
| `TypeError: '>' str and int` | Form envia string, model compara com int | Cast em `_apply_fields` via `_int_fields` |
| Blueprint não encontrado | `url_prefix` ausente ou errado | Verificar prefixo e se auto-discovery alcança o módulo |
| CSV com encoding errado | StringIO sem BOM | `output.write('\ufeff')` antes do writer |
| Enum exibe `EnumName.VALUE` | `str(enum_obj)` retorna repr | `enum_obj.value` ou filtro `smart_val` |
