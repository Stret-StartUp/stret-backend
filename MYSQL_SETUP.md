# MySQL setup

Crie um banco MySQL chamado `eventrank`.

```sql
CREATE DATABASE eventrank CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Configure o arquivo `.env` na raiz do projeto:

```env
MYSQL_DRIVER=mysql+aiomysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=eventrank
MYSQL_USER=eventrank_user
MYSQL_PASSWORD=sua_senha
CREATE_DATABASE_TABLES_ON_STARTUP=false
```

O backend monta a `DATABASE_URL` automaticamente a partir dessas variaveis.
Isso evita problemas com senhas que tenham caracteres especiais como `@`, `#`, `/` ou `:`.

Se preferir informar a URL manualmente, tambem funciona:

```env
DATABASE_URL=mysql+aiomysql://eventrank_user:sua_senha@localhost:3306/eventrank?charset=utf8mb4
```

Nesse caso, se a senha tiver caracteres especiais como `@`, `#`, `/` ou `:`, use URL encoding
na `DATABASE_URL`.

O erro `Access denied for user 'user'@'localhost'` significa que o `.env`
ainda esta usando o placeholder `user:password`. O erro `Access denied for user
'root'@'localhost'` normalmente significa senha incorreta ou usuario sem permissao
para conectar por TCP.

Voce pode criar um usuario dedicado no MySQL com:

```sql
CREATE USER 'eventrank_user'@'localhost' IDENTIFIED BY 'sua_senha';
GRANT ALL PRIVILEGES ON eventrank.* TO 'eventrank_user'@'localhost';
FLUSH PRIVILEGES;
```

Instale as dependencias e crie as tabelas:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.db.check_connection
.\.venv\Scripts\python.exe -m app.db.init_db
```

Suba a API:

```powershell
.\.venv\Scripts\python.exe run.py
```

`POST /api/v1/upload` salva o evento na tabela `event` e os clientes do Excel na tabela `customer`.
As rotas `POST /api/v1/query` e `POST /api/v1/profile` leem o historico salvo no MySQL pelo `client_id`.
