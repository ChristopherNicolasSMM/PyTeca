## 🚀 Plano de Execução – Módulos Administrativos do Pyteca

### Fase 0 – Fundação (1-2 dias)
- Criar modelos de dados (`system_config`, `model_definition`, `scheduled_task`, `message_queue`, `task_log`, `query_log`).
- Adicionar permissão básica (`admin_required` decorator).
- Estruturar pastas: `controller/admin/`, `services/admin/`, `api/routes/core/builder/`, `templates/admin/`.
- Configurar logging e cache simples para configurações.

### Fase 1 – Central de Configurações (2-3 dias)
- **Serviço**: `ConfigService` com cache (memória/redis) e fallback para banco.
- **API**: endpoints CRUD para configurações (apenas admin).
- **UI**: página com abas (grupos), formulários dinâmicos, botão salvar.
- **Valor entregue**: parâmetros do sistema editáveis pela interface.

### Fase 2 – Model Builder Visual (3-4 dias)
- **Modelo**: `model_definition` (já criado).
- **Serviço**: `ModelGenerator` – gera arquivo `.py` a partir da definição, usando os templates `.j2` existentes.
- **API**: endpoints para salvar definição, pré-visualizar código, gerar modelo e opcionalmente rodar `flask generate` para criar CRUD.
- **UI**: formulário com editor de campos (add/remover linhas), seleção de anotações, Ace Editor para pré-visualização.
- **Integração**: após gerar o modelo, o sistema pode recarregar blueprints (em dev) ou solicitar reinício.
- **Valor entregue**: criação de modelos sem escrever código.

### Fase 3 – Query & API Playground (3-4 dias)
- **SQL Playground**:
  - Endpoint que executa apenas `SELECT` (validação com `sqlparse` ou regex).
  - Logs em `query_log`.
  - Editor SQL (Ace Editor) na UI, resultado em tabela.
- **API Playground**:
  - Proxy HTTP com whitelist de domínios (lida da `system_config`).
  - Logs em `api_log`.
  - Botão "Gerar Model a partir da resposta" → chama o Model Builder (Fase 2) pré-preenchido.
- **Valor entregue**: ferramenta de teste e integração, acelera o desenvolvimento de integrações.

### Fase 4 – Scheduler e Mensageria (4-5 dias)
- **Backend**:
  - APScheduler integrado ao Flask (iniciado em `create_app`).
  - Job que processa `MessageQueue` a cada 10 segundos.
  - Job que verifica `ScheduledTask` vencidas e as executa.
  - TaskLog para cada execução.
- **API**: endpoints para CRUD de tarefas, aprovar/rejeitar, executar agora, visualizar fila.
- **UI**:
  - Página de tarefas agendadas (SmartList com ações customizadas).
  - Página da fila de mensagens (listagem, reprocessar, cancelar).
  - Dashboards com gráficos (ApexCharts): execuções por dia, status, tarefas mais lentas.
- **Valor entregue**: automação de tarefas recorrentes e processamento assíncrono.

### Fase 5 – Perfis de Acesso (RBAC) – por último (3-4 dias)
- **Modelos**: `Role`, `Permission`, `UserRole`.
- **Lógica**: decorator `@permission_required('perm_name')` e adaptação do menu para exibir apenas itens permitidos.
- **UI**: tela de gestão de papéis e permissões (apenas super-admin).
- **Valor entregue**: segurança e delegação de responsabilidades.

---

## 🎯 Sugestão de Ordem para Máximo Aproveitamento

**Inicie pela Fase 0 + Fase 1 (Configurações)** – é a base para as demais (whitelist, parâmetros).  
**Depois Fase 2 (Model Builder)** – permite criar modelos rapidamente, inclusive os necessários para testar as próximas fases.  
**Em seguida Fase 3 (Playground)** – útil para testar APIs externas e gerar modelos a partir delas.  
**Depois Fase 4 (Scheduler)** – mais complexa, mas agora com infraestrutura pronta.  
**Por último Fase 5 (RBAC)** – como solicitado.

Essa ordem entrega valor incremental a cada sprint e mantém as dependências sob controle.

---

## ✅ Próximo Passo Concreto

Vou começar a implementar a **Fase 0** (modelos e estrutura) e já enviar o código para você testar. Assim que você confirmar, gerarei os arquivos:

- Modelos (`system_config`, `model_definition`, etc.)
- Decorator `admin_required`
- Estrutura de pastas

**Aguardo sua confirmação para iniciar a codificação.**