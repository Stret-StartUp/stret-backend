# EventRank Backend

## Visao geral

O EventRank Backend e uma API em FastAPI para ajudar produtores de eventos a
entenderem sua base historica de consumidores e ranquearem quais clientes tem
maior chance de comprar ingresso para um novo evento.

A ideia principal da aplicacao nao e processar tudo em uma chamada isolada.
O fluxo foi pensado para acumular varios eventos historicos de um mesmo cliente
produtor e, depois, usar esse historico maior para responder uma query sobre um
novo evento.

## Problema que o projeto resolve

Produtores de eventos normalmente tem planilhas com compradores de eventos
passados, mas esses dados ficam pouco aproveitados. O backend transforma esses
arquivos em uma base historica consultavel e usa caracteristicas dos eventos
anteriores para estimar quais consumidores combinam melhor com um evento alvo.

Exemplo:

- Um produtor envia historicos de festas universitarias, open bar, eventos
  premium, festas de funk, eventos corporativos etc.
- Depois ele cadastra o escopo de um novo evento.
- A API cruza o perfil do evento alvo com o comportamento historico dos
  consumidores.
- A resposta e um Excel com ranking dos consumidores mais promissores.

## Fluxo principal da aplicacao

### 1. Upload de historico

Endpoint:

```text
POST /api/v1/upload
```

Responsabilidade:

- receber um arquivo Excel de compradores de um evento historico;
- receber as caracteristicas estruturadas desse evento historico;
- transformar a planilha em consumidores agregados;
- salvar o evento e seus consumidores no MySQL;
- permitir varios uploads para o mesmo `client_id`.

Esse endpoint alimenta a base historica.

### 2. Query de evento alvo

Endpoint:

```text
POST /api/v1/query
```

Responsabilidade:

- receber o `client_id`;
- receber as caracteristicas estruturadas do novo evento;
- buscar todo o historico salvo para esse `client_id`;
- calcular score de afinidade entre consumidores historicos e evento alvo;
- retornar um Excel com os consumidores ranqueados.

Esse endpoint e o principal para tomada de decisao.

### 3. Perfil de consumidor

Endpoint:

```text
POST /api/v1/profile
```

Responsabilidade:

- receber o `client_id`;
- receber o escopo do evento alvo;
- analisar a base historica salva;
- gerar um texto explicando o perfil de consumidor mais aderente.

## Rotas publicas atuais

```text
GET  /health
POST /api/v1/upload
POST /api/v1/query
POST /api/v1/profile
```

O antigo endpoint `/api/v1/process` foi removido do roteador publico porque ele
processava um arquivo isolado em uma unica chamada. Esse comportamento nao
representava o fluxo esperado do produto, que depende de historico acumulado.

## Campos estruturados de evento

Os mesmos campos sao usados para o evento historico no `upload` e para o evento
alvo no `query` e no `profile`.

```text
category
price
location
size
vibe
audience_type
colleges
genres
themes
artists
brands
event_description
```

Descricao dos campos:

- `category`: categoria ou tipo do evento, como festa, show, palestra ou evento corporativo.
- `price`: preco esperado ou medio do ingresso.
- `location`: cidade, bairro, venue ou regiao do evento.
- `size`: tamanho esperado, como pequeno, medio, grande ou festival.
- `vibe`: estilo percebido do evento, como premium, alternativo, universitario, corporativo ou sujeira.
- `audience_type`: publico tipico, como universitario, corporativo ou geral.
- `colleges`: faculdades relacionadas ao publico, quando fizer sentido.
- `genres`: generos musicais, como funk, eletronico, pagode, sertanejo.
- `themes`: temas do evento, como open bar, formatura, networking, carnaval.
- `artists`: artistas, DJs, palestrantes ou atracoes de interesse.
- `brands`: marcas ou patrocinadores associados ao publico.
- `event_description`: texto livre opcional para complementar os campos estruturados.

Campos de lista aceitam texto separado por virgula, ponto e virgula, quebra de
linha ou `|`.

Exemplo:

```text
genres=funk, eletronico
colleges=Insper, FGV, ESPM
artists=DJ X, Banda Y
brands=Red Bull, Beats
```

## Dados analisados para perfil de consumidor

A analise historica considera:

- eventos que o consumidor ja participou;
- ticket medio que costuma pagar;
- antecedencia de compra inferida pelo lote;
- generos musicais e temas historicos;
- artistas, palestrantes e marcas de interesse;
- idade;
- faculdade e cidade;
- frequencia de compra;
- preferencia por vibe/qualidade, como premium, popular ou sujeira.

## Como o ranking e calculado

O score final e uma soma ponderada de fatores:

```text
affinity_score
ticket_score
age_score
purchase_timing_score
vibe_score
frequency_score
```

Pesos padrao:

```text
AFFINITY_WEIGHT=0.30
TICKET_WEIGHT=0.20
AGE_WEIGHT=0.15
PURCHASE_TIMING_WEIGHT=0.15
VIBE_WEIGHT=0.10
FREQUENCY_WEIGHT=0.10
```

O backend compara o evento alvo com os historicos salvos. Quanto mais proximo o
historico de um consumidor estiver do escopo do evento alvo, maior tende a ser
o score.

## Banco de dados

O projeto usa MySQL com SQLAlchemy assincrono via `aiomysql`.

Tabelas principais:

- `event`: representa um evento historico enviado por upload.
- `customer`: representa os consumidores extraidos do Excel daquele evento.

O campo `event.description` armazena as caracteristicas estruturadas do evento
historico em JSON serializado. Isso permite evoluir o modelo de evento sem
precisar criar uma migration imediata para cada novo campo.

## Configuracao de ambiente

O projeto carrega variaveis do arquivo `.env` usando `python-dotenv` e
`pydantic-settings`.

Formato recomendado:

```env
MYSQL_DRIVER=mysql+aiomysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=eventrank
MYSQL_USER=eventrank_user
MYSQL_PASSWORD=sua_senha
CREATE_DATABASE_TABLES_ON_STARTUP=false
```

Tambem e possivel informar uma URL completa:

```env
DATABASE_URL=mysql+aiomysql://eventrank_user:sua_senha@localhost:3306/eventrank?charset=utf8mb4
```

Quando `DATABASE_URL` estiver definida, ela tem prioridade sobre as variaveis
`MYSQL_*`.

## Como rodar localmente

Instalar dependencias:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Testar conexao com MySQL:

```powershell
.\.venv\Scripts\python.exe -m app.db.check_connection
```

Criar tabelas:

```powershell
.\.venv\Scripts\python.exe -m app.db.init_db
```

Subir a API:

```powershell
.\.venv\Scripts\python.exe run.py
```

Documentacao interativa:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

## Estrutura principal do codigo

```text
app/main.py
app/core/config.py
app/db/session.py
app/db/init_db.py
app/db/check_connection.py
app/api/v1/api.py
app/api/v1/endpoints/upload.py
app/api/v1/endpoints/query.py
app/api/v1/endpoints/profile.py
app/services/ingestion/transform_service.py
app/services/ingestion/parser_service.py
app/services/ingestion/database_storage_service.py
app/services/analytics/scoring_service.py
app/services/analytics/insight_service.py
app/repositories/event_repository.py
app/models/event.py
app/models/customer.py
```

## Estado atual do projeto

O backend ja possui:

- API FastAPI;
- upload de Excel;
- transformacao dos dados de compradores;
- persistencia em MySQL;
- fluxo de historico por `client_id`;
- query estruturada de evento alvo;
- ranking exportado em Excel;
- perfil textual de consumidor;
- configuracao por `.env`;
- script de teste de conexao com banco;
- criacao automatica de tabelas via `app.db.init_db`;
- modulo inicial de ML para gerar dataset treinavel em `app/ml/build_training_data.py`;
- baseline supervisionado com `scikit-learn` em `app/ml/train_model.py`.

## Evolucao para Machine Learning

A primeira fase de ML ja transforma o historico salvo no MySQL em um dataset
supervisionado.

Problema de treino:

```text
Entrada: (cliente, evento)
Saida: comprou ou nao comprou
```

Labels:

```text
1 = cliente comprou o evento alvo
0 = cliente nao comprou o evento alvo
```

O dataset reutiliza as features do ranking atual:

```text
affinity_score
ticket_score
age_score
purchase_timing_score
vibe_score
frequency_score
score
```

Comando:

```powershell
.\.venv\Scripts\python.exe -m app.ml.build_training_data
```

Output:

```text
app/ml/data/training_dataset.csv
```

Mais detalhes estao em `ML_PIPELINE.md`.

A segunda fase de ML tambem ja treina baselines supervisionados:

```powershell
.\.venv\Scripts\python.exe -m app.ml.train_model
```

Modelos treinados:

```text
logistic_regression
random_forest
```

Outputs locais:

```text
app/ml/models/baseline_model.joblib
app/ml/reports/baseline_metrics.json
```

## Proximos passos sugeridos

- Criar migrations com Alembic para evoluir o schema com seguranca.
- Persistir campos estruturados de evento em colunas proprias ou JSON nativo.
- Criar endpoint para listar historicos ja enviados por `client_id`.
- Criar endpoint para deletar ou substituir um upload historico.
- Separar treino/teste por evento para avaliar o ranking de forma mais realista.
- Integrar o modelo treinado no endpoint `/api/v1/query`.
- Criar fallback para usar o score heuristico quando nao existir modelo treinado.
- Melhorar o scoring com calibracao baseada em resultados reais de venda.
- Adicionar testes automatizados para parser, transformacao e scoring.
