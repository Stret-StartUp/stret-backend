# API flow

O fluxo principal usa historico acumulado com pipeline de 3 etapas:

## 1. Upload de Histórico

`POST /api/v1/upload`
- Salva um evento histórico e os consumidores do Excel no MySQL.
- Pode ser chamado varias vezes para o mesmo `client_id`.

## 2. Query - Ranking de Consumidores (FLUXO PRINCIPAL)

`POST /api/v1/query`
- Recebe o escopo do evento alvo.
- Executa pipeline de 3 etapas:

### ETAPA 1: Ranking de Eventos
- Compara evento alvo com todos os eventos históricos.
- Calcula score de similaridade para cada evento (0.0 a 1.0).
- Retorna eventos ordenados por similaridade.

### ETAPA 2: Avaliação de Consumidores
- Coleta consumidores dos eventos similares.
- Categoriza cada consumidor por similaridade do seu evento:
  - **HIGH** (score >= 0.7): Eventos muito similares
  - **MEDIUM** (score 0.4-0.7): Eventos medianamente similares
  - **LOW** (score < 0.4): Eventos pouco similares
- **Importante**: Consumidores em eventos similares recebem peso maior.

### ETAPA 3: Scoring Final
- Agrega consumidores por email.
- Calcula score final para evento alvo com pesos:
  - Similaridade do evento: **2.5x** (principal fator - novo!)
  - Afinidade: 1.0x
  - Preço: 1.0x
  - Idade: 0.5x
  - Frequência de compra: 1.0x
  - Timing de compra: 1.0x
  - Vibe: 0.5x
- Retorna Excel com consumidores ranqueados.

## 3. Profile - Análise de Perfil

`POST /api/v1/profile`
- Recebe o escopo do evento alvo.
- Analisa o perfil de consumidor a partir do historico salvo.

---

## Mudanças na Lógica

### Antes
- Todos os consumidores tinha peso igual, independente da similaridade do evento que apareciam.

### Agora
- Consumidores em eventos muito similares (score 0.9) têm peso 3x maior que em eventos pouco similares (score 0.3).
- Ponderação explícita por categoria de evento (HIGH/MEDIUM/LOW).
- Score de similaridade do evento é fator principal (2.5x de peso).

---

`/api/v1/process` foi removido do roteador publico.

## Campos de evento

Use os mesmos campos para evento historico no `upload` e evento alvo no `query`/`profile`:

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

Campos de lista aceitam texto separado por virgula, ponto e virgula, quebra de linha ou `|`.

Exemplo:

```text
genres=funk, eletronico
colleges=Insper, FGV, ESPM
artists=DJ X, Banda Y
brands=Red Bull, Beats
```

`upload` ainda aceita `past_event_description` temporariamente por compatibilidade, mas o caminho recomendado e usar os campos estruturados acima.
