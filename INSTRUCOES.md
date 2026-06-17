# Instruções de aplicação — fix2

## 1. Instalar pacotes novos

```bash
pip install apscheduler==3.10.4 croniter==2.0.5
```

## 2. Aplicar os arquivos

Descompacte o zip e copie sobre a pasta `src/`:

```bash
unzip -o pyteca_fix2.zip -d /caminho/para/pyteca
```

## 3. Integrar o TaskService ao main.py

No final de `create_app()`, antes do `return app`, adicione:

```python
# Scheduler de tarefas (APScheduler)
from services.core.admin.task_service import TaskService
TaskService.init_scheduler(app)
```

## 4. Configurar whitelist da API Playground (opcional)

Na página `/admin/config`, adicione a chave:

- **Chave:** `API_WHITELIST`
- **Tipo:** `string`
- **Grupo:** `seguranca`
- **Valor:** `api.github.com, jsonplaceholder.typicode.com` (domínios separados por vírgula)

Se `API_WHITELIST` estiver vazia, qualquer domínio público é permitido (IPs privados são sempre bloqueados).

## 5. Registrar funções Python elegíveis como tarefas (opcional)

Em `services/core/admin/task_service.py`, adicione suas funções ao `TASK_REGISTRY`:

```python
from services.meu_servico import minha_funcao

TASK_REGISTRY = {
    "backup_db": minha_funcao,
}
```

## Resumo dos arquivos alterados

| Arquivo | Mudança |
|---|---|
| `model/bookstore/author.py` | Adicionado `@display_field("name")` |
| `templates/menu_complementar.yaml` | Entrada `admin.users` comentada (evita 404) |
| `api/routes/core/builder/query_api.py` | SQL Playground implementado (SELECT-only, log) |
| `api/routes/core/builder/playground_api.py` | API Proxy implementado (whitelist, log) |
| `api/routes/core/admin/task_api.py` | **NOVO** — API REST completa de tarefas e fila |
| `api/routes/core/admin/__init__.py` | **NOVO** |
| `services/core/admin/task_service.py` | Implementação real (CRUD, run_now, queue, APScheduler) |
| `templates/core/builder/query_playground.html` | UI completa com Ace Editor, abas SQL/API, histórico |
| `templates/core/admin/task_monitor.html` | UI completa com cards, gráfico, SmartList, fila, logs |
