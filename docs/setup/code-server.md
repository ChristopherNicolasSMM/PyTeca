# Setup — code-server (VS Code via navegador) no Debian

## O que é e por que esta abordagem

[code-server](https://github.com/coder/code-server) é o VS Code real,
compilado para rodar como serviço num servidor Linux e servido via
navegador. Não é uma reimplementação — é o mesmo editor, com extensões,
terminal integrado, debugger e Git.

**Decisão tomada**: abandonar a ideia de construir um console/IDE
embutido no PyTeca. Editar código de verdade (criar arquivo, rodar
comando, debugar) é trabalho de ferramenta de desenvolvimento madura —
reconstruir isso dentro da aplicação Flask seria reinventar, com mais
risco de segurança e menos capacidade, algo que já existe pronto e
mantido por terceiros.

O que **fica** dentro do PyTeca é só a tela de **histórico e diff de
versões** (recuperar e comparar o que o sistema de versionamento já
capturou) — ver `docs/manual/09-historico-versoes.md`. Edição de arquivo
de fato acontece aqui, no code-server.

---

## 1. Instalação

```bash
# Como root ou com sudo
curl -fsSL https://code-server.dev/install.sh | sh
```

Isso instala o `code-server` como pacote `.deb` (Debian/Ubuntu) e já
registra um serviço systemd chamado `code-server@<usuario>`.

## 2. Autenticação por usuário do sistema (PAM)

Por padrão, o code-server usa uma senha fixa gerada automaticamente,
guardada em `~/.config/code-server/config.yaml`. Isso **não** é o que
você quer — você pediu login com usuário/senha do próprio servidor.

O code-server suporta autenticação via **PAM** (Pluggable Authentication
Modules), que usa as mesmas credenciais de login do Linux — exatamente o
"usuários do servidor" que você mencionou.

### Habilitar autenticação PAM

```bash
sudo nano /etc/code-server/config.yaml
```

Conteúdo:

```yaml
bind-addr: 127.0.0.1:8080
auth: password
password: ""          # deixe vazio quando usar PAM — ver abaixo
cert: false
```

O code-server **não tem PAM nativo embutido na versão open source padrão**
— a forma correta e suportada de "logar com usuário do sistema" é combinar
duas camadas, que é também a abordagem mais segura:

### Abordagem recomendada: Nginx com autenticação PAM (via `pam_module` do Nginx) + code-server sem exposição direta

Como o Nginx tradicional não tem autenticação PAM nativa de fábrica
(depende de módulo extra, `libnginx-mod-http-auth-pam`, disponível nos
repositórios Debian), esse é o caminho mais simples e auditável:

```bash
sudo apt install nginx libnginx-mod-http-auth-pam
```

Configuração do site (`/etc/nginx/sites-available/code-server`):

```nginx
server {
    listen 443 ssl;
    server_name seu-dominio.com;

    ssl_certificate     /etc/letsencrypt/live/seu-dominio.com/fullchain.pem;
    ssl_certificate_key  /etc/letsencrypt/live/seu-dominio.com/privkey.pem;

    # Autenticação via usuários reais do Linux (PAM)
    auth_pam            "Acesso restrito - PyTeca Dev";
    auth_pam_service_name "nginx-codeserver";

    location / {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection upgrade;
        proxy_set_header Accept-Encoding gzip;
    }
}

server {
    listen 80;
    server_name seu-dominio.com;
    return 301 https://$host$request_uri;
}
```

Arquivo PAM dedicado (`/etc/pam.d/nginx-codeserver`):

```
auth     required pam_unix.so
account  required pam_unix.so
```

Isso faz o Nginx pedir usuário/senha (via popup HTTP Basic Auth do
navegador) **antes** de qualquer requisição chegar ao code-server, e a
validação é literalmente contra `/etc/passwd` + `/etc/shadow` — os
mesmos usuários que existem no Debian. Sem usuário válido do sistema,
não entra.

```bash
sudo systemctl reload nginx
```

### Por que essa camada extra, e não só o `auth: password` do code-server

O `auth: password` simples do code-server guarda uma senha única
compartilhada — não distingue "quem" logou, e não usa contas reais do
sistema. A combinação Nginx+PAM resolve exatamente o que você pediu:
login por usuário do servidor, antes de acessar o link.

## 3. HTTPS obrigatório

Nunca exponha isso sem TLS — a sessão (incluindo a senha PAM trafegada
via Basic Auth) precisa estar criptografada.

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d seu-dominio.com
```

Renovação automática já vem configurada pelo certbot via systemd timer
— confirme com `sudo certbot renew --dry-run`.

## 4. Restringir o code-server a só aceitar conexões locais

O `bind-addr: 127.0.0.1:8080` no `config.yaml` do code-server (passo 2)
já garante que ele só escuta localmente — **só o Nginx consegue
alcançá-lo**, ninguém pode pular direto para a porta 8080 driblando a
autenticação PAM. Confirme com:

```bash
sudo ss -tlnp | grep 8080
# Deve mostrar 127.0.0.1:8080, nunca 0.0.0.0:8080
```

## 5. Abrir o projeto PyTeca diretamente

```bash
sudo systemctl edit code-server@seu_usuario
```

Adicione (ou ajuste o `ExecStart` para incluir o caminho):

```ini
[Service]
ExecStart=
ExecStart=/usr/lib/code-server/bin/code-server --bind-addr 127.0.0.1:8080 /caminho/para/PyTeca
```

```bash
sudo systemctl restart code-server@seu_usuario
sudo systemctl enable code-server@seu_usuario   # inicia com o boot do servidor
```

## 6. Checklist final de segurança

- [ ] `bind-addr` do code-server é `127.0.0.1`, nunca `0.0.0.0`
- [ ] Nginx exige HTTPS (porta 80 redireciona para 443)
- [ ] `auth_pam` configurado e testado com um usuário real
- [ ] Usuário usado para login **não é root** — crie um usuário Linux
      dedicado (`sudo adduser dev-pyteca`) com acesso só à pasta do projeto
- [ ] Firewall (`ufw`) só libera 443 (e 22 para SSH) externamente:
      ```bash
      sudo ufw allow 443/tcp
      sudo ufw allow 22/tcp
      sudo ufw enable
      ```
- [ ] Considere fail2ban para a porta 443, mitigando brute-force contra
      o Basic Auth PAM

## 7. Uso no dia a dia

Acesse `https://seu-dominio.com`, autentique com usuário/senha do
servidor, e você tem o VS Code completo: editor, terminal integrado
(`Ctrl+\``, já no diretório do PyTeca), Git, extensões Python.

Para reiniciar o Flask depois de editar:

```bash
# No terminal integrado do code-server
sudo systemctl restart pyteca   # ou o nome do seu serviço systemd do Flask
```

Isso é deliberadamente manual — reiniciar o servidor automaticamente a
partir de uma ação na própria aplicação é exatamente o tipo de
funcionalidade arriscada (equivalente a RCE) que foi descartada junto
com a ideia do console Python embutido.
