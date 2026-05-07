# ML pipeline

## Objetivo

Evoluir o backend de ranking por regras para um sistema com Machine Learning
integrado.

A primeira fase cria um dataset treinavel a partir do historico ja salvo no
MySQL.

## Fase 1: dataset de treino

Modulo:

```text
app/ml/build_training_data.py
```

Output padrao:

```text
app/ml/data/training_dataset.csv
```

Esse CSV e gerado localmente e nao deve ser versionado, pois contem dados de
clientes como e-mail.

## Definicao do problema

Entrada:

```text
(cliente, evento)
```

Saida:

```text
comprou
```

Labels:

```text
1 = cliente comprou o evento alvo
0 = cliente nao comprou o evento alvo
```

## Como o dataset e construido

Para cada evento historico salvo:

1. O evento vira o `target_event`.
2. Os clientes que compraram esse evento viram exemplos positivos.
3. Clientes de outros eventos do mesmo `client_id` que nao compraram esse evento
   viram exemplos negativos.
4. O script calcula as mesmas features usadas no ranking atual.
5. As linhas sao salvas em CSV.

Para reduzir vazamento de dados, o script nao usa a compra do proprio evento
alvo para montar as features do cliente. O cliente precisa aparecer em pelo
menos outro evento historico para virar uma linha treinavel.

Isso significa que compradores que aparecem somente no evento alvo sao contados
como positivos sem historico, mas nao entram no dataset de treino.

## Features reutilizadas

As features numericas reaproveitam o scoring atual:

```text
affinity_score
ticket_score
age_score
purchase_timing_score
vibe_score
frequency_score
score
```

Metadados tambem sao salvos para auditoria:

```text
client_id
target_event_id
customer_email
history_event_count
history_event_ids
target_category
target_price
target_location
target_size
target_vibe
target_audience_type
target_colleges
target_genres
target_themes
target_artists
target_brands
customer_age
customer_city
customer_college
customer_avg_ticket
customer_purchase_frequency
```

## Comando

Gerar dataset com amostragem padrao de 3 negativos por positivo:

```powershell
.\.venv\Scripts\python.exe -m app.ml.build_training_data
```

Informar caminho de saida:

```powershell
.\.venv\Scripts\python.exe -m app.ml.build_training_data --output app\ml\data\training_dataset.csv
```

Filtrar por cliente:

```powershell
.\.venv\Scripts\python.exe -m app.ml.build_training_data --client-id cliente_123
```

Alterar proporcao de negativos:

```powershell
.\.venv\Scripts\python.exe -m app.ml.build_training_data --negative-ratio 5
```

Usar todos os negativos elegiveis:

```powershell
.\.venv\Scripts\python.exe -m app.ml.build_training_data --all-negatives
```

## Resultado da primeira geracao local

Na base atual configurada no `.env`, a primeira execucao gerou:

```text
Eventos encontrados: 3
Eventos usados: 2
Linhas positivas: 684
Linhas negativas: 1694
Total de linhas: 2378
Compradores positivos sem historico previo em outros eventos: 2627
```

Arquivo:

```text
app/ml/data/training_dataset.csv
```

## Proximas fases sugeridas

### Fase 2: baseline supervisionado

- Treinar um modelo simples com `scikit-learn`.
- Comecar com `LogisticRegression` e `RandomForestClassifier`.
- Separar treino/teste por evento, nao por linha, para reduzir vazamento.
- Medir AUC, precision@k e recall@k.

Modulo implementado:

```text
app/ml/train_model.py
```

Comando:

```powershell
.\.venv\Scripts\python.exe -m app.ml.train_model
```

O script treina dois baselines:

```text
logistic_regression
random_forest
```

Features usadas:

```text
affinity_score
ticket_score
age_score
purchase_timing_score
vibe_score
frequency_score
score
```

Split:

```text
GroupShuffleSplit por target_event_id
```

Isso evita misturar linhas do mesmo evento em treino e teste.

Outputs:

```text
app/ml/models/baseline_model.joblib
app/ml/reports/baseline_metrics.json
```

Esses arquivos sao gerados localmente e nao devem ser versionados.

Resultado da primeira execucao local:

```text
Melhor modelo: random_forest
Train rows: 1010
Test rows: 1368
Train events: [2]
Test events: [4]

roc_auc: 0.6479
average_precision: 0.3619
log_loss: 0.7304
precision_at_50: 0.46
recall_at_50: 0.0673
precision_at_100: 0.60
recall_at_100: 0.1754
```

Observacao: a base atual ainda tem poucos eventos-alvo treinaveis. As metricas
devem ser vistas como sanity check tecnico, nao como avaliacao final de
performance do produto.

### Fase 3: persistir modelo

- Salvar artefato treinado em `app/ml/models/`.
- Criar script `train_model.py`.
- Criar script `evaluate_model.py`.

### Fase 4: servir predicao na API

- Usar o modelo treinado dentro de `/api/v1/query`.
- Manter fallback para o score heuristico atual.
- Retornar `ml_score`, `heuristic_score` e ranking combinado.

### Fase 5: feedback loop

- Registrar se o cliente realmente comprou depois da recomendacao.
- Alimentar labels reais, nao apenas labels derivados de historico.
- Re-treinar periodicamente.
