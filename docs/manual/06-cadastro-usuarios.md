# 06 — Cadastro de Usuários

## Decisão de produto

O cadastro de novo usuário **não é público** — só um administrador pode
criar contas, através da tela `/admin/roles` (mesma tela de gestão de
papéis, seção "Usuários").

Existe no código um fluxo de auto-cadastro órfão (`api/routes/core/register.py`
+ `templates/core/register.html` + model `RegistrationRequest`), herdado de
um projeto anterior ("BrewStation" — termos como `experience: brewer` e
e-mails de `@brewstation.com` aparecem no código). **Esse fluxo não foi
removido** (fora do escopo desta entrega) mas está documentado aqui como
código morto, candidato a remoção futura. O cadastro real do PyTeca é
`POST /register` em `controller/core/auth.py`, que continua existindo só
para compatibilidade — a via oficial de criação passou a ser
`/api/admin/users` (admin-only).

## Campos do usuário

| Campo | Obrigatório? | Coluna no banco | Observação |
|---|---|---|---|
| Login | Sim | `username` | único |
| Nickname | Sim | `nome` | já era usado em todo o projeto como nome de exibição curto (header, saudações) — mantido o mesmo nome de coluna |
| Nome completo | Sim | `nome_completo` | |
| E-mail | Sim | `email` | único, validado por formato |
| Celular | Sim | `celular` | novo campo — diferente de `telefone` (que já existia, opcional, mantido sem alteração) |
| Senha | Sim (na criação) | `password_hash` | opcional na edição — em branco mantém a senha atual |
| CPF | Não | `cpf` | validado por dígito verificador real, único se informado |
| Rua / Número / Complemento / Bairro / Cidade / UF / CEP | Não | `endereco_*` | campos separados (decisão de produto), endereço antigo (`endereco` texto livre) preservado por compatibilidade |

## Validação de CPF

`utils/validators.py` implementa o algoritmo oficial dos dois dígitos
verificadores — não é apenas checagem de formato/máscara. Também rejeita
sequências repetidas (`111.111.111-11`, `000.000.000-00`, etc.), que
passam o algoritmo matematicamente mas são sempre fraudulentas.

```python
from utils.validators import validate_cpf, format_cpf

validate_cpf("111.444.777-35")  # True  — CPF de teste válido
validate_cpf("111.111.111-11")  # False — sequência repetida
validate_cpf("123.456.789-00")  # False — dígito verificador errado
```

`User.set_cpf(cpf)` chama essa validação e lança `ValueError` se inválido
— a camada de API captura isso e devolve HTTP 422 com mensagem amigável,
nunca deixa propagar como erro 500.

## API — `/api/admin/users`

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/` | Lista todos os usuários |
| `GET` | `/<id>` | Detalhe de um usuário |
| `POST` | `/` | Cria usuário (senha obrigatória) |
| `PUT` | `/<id>` | Edita usuário (senha opcional — vazio mantém a atual) |
| `POST` | `/<id>/deactivate` | Desativa (soft) — não pode mais logar |
| `POST` | `/<id>/activate` | Reativa |

**Por que não há `DELETE`**: excluir usuário de verdade apaga rastro de
quem criou/editou registros no sistema. Desativar é reversível e segue o
mesmo padrão soft-delete usado no resto do projeto (Book, Loan, Author).

## UI

A tela `/admin/roles` (já existente para gestão de Roles/Permissions)
ganhou uma seção de Usuários expandida: botão "Novo Usuário" abre um modal
com todos os campos (identidade obrigatória, CPF opcional, endereço
opcional), e cada linha da tabela tem botão de editar e
ativar/desativar.

A listagem de usuários (`GET /api/admin/roles/users`) foi estendida para
incluir os novos campos, evitando que a UI precise combinar duas chamadas
de API diferentes para montar uma única tabela.

## O que não foi alterado

- `telefone` (campo antigo, opcional) continua existindo sem mudança —
  `celular` é um campo novo e distinto, não uma renomeação.
- `endereco` (texto livre, antigo) foi mantido por compatibilidade com
  qualquer lugar que ainda o leia — o cadastro novo usa os campos
  separados (`endereco_rua`, `endereco_cidade`, etc.) exclusivamente.
- O fluxo de login (`POST /login`) não foi tocado.
  