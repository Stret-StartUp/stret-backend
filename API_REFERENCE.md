# API Reference

## Health check

GET /health

Response:

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

## Upload de histórico

POST /api/v1/upload

Form fields:

- `file`: Excel com dados dos compradores
- `client_id`: identificador do cliente/produtor
- `past_event_description`: descrição histórica do evento (opcional)
- `event_description`: descrição do evento atual/histórico
- `category`: categoria do evento
- `price`: preço médio esperado
- `location`: local, cidade ou região
- `size`: tamanho do evento
- `vibe`: vibe/estilo do evento
- `audience_type`: tipo de público
- `colleges`: faculdades relacionadas
- `genres`: gêneros musicais
- `themes`: temas do evento
- `artists`: artistas ou atrações
- `brands`: marcas associadas

Retorno:

```json
{
  "message": "Dados armazenados com sucesso",
  "event_id": 123,
  "customers_saved": 456,
  "processing_time_seconds": 12.34
}
```

---

## Query de ranking

POST /api/v1/query

Form fields:

- `client_id`
- `event_description`
- `category`
- `price`
- `location`
- `size`
- `vibe`
- `audience_type`
- `colleges`
- `genres`
- `themes`
- `artists`
- `brands`

Retorno:

- arquivo Excel com o ranking dos consumidores

Erro quando não há histórico:

```json
{ "error": "Nenhum dado encontrado para esse cliente" }
```

---

## Perfil textual

POST /api/v1/profile

Form fields:

- `client_id`
- `event_description`
- `category`
- `price`
- `location`
- `size`
- `vibe`
- `audience_type`
- `colleges`
- `genres`
- `themes`
- `artists`
- `brands`

Retorno:

```json
{
  "profile": "Texto descritivo do perfil de público..."
}
```

---

## Histórico de uploads

GET /api/v1/history?client_id={client_id}

Response:

```json
{
  "client_id": "cliente_123",
  "total_events": 2,
  "events": [
    {
      "id": 12,
      "file_name": "event.xlsx",
      "created_at": "2026-05-21T...",
      "customers_count": 120,
      "avg_age": 24.7,
      "avg_ticket": 95.0,
      "summary": "Evento universitário, funk...",
      "features": {
        "category": "festa",
        "price": 80.0,
        "location": "São Paulo",
        "size": "grande",
        "vibe": "sujeira",
        "audience_type": "universitário",
        "colleges": "Insper",
        "genres": "funk",
        "themes": "open bar",
        "artists": "DJ X",
        "brands": "Beats"
      }
    }
  ]
}
```

---

## Co-attendance / clientes mais conectados

POST /api/v1/analytics/most-connected

Form fields:

- `client_id`
- `top_n` (default: 50)
- `min_shared_events` (default: 1)
- `top_partners` (default: 5)

Retorno:

```json
{
  "client_id": "cliente_123",
  "total_events": 5,
  "total_customers": 180,
  "total_edges": 34,
  "top_customers": [
    {
      "email": "a@example.com",
      "events_count": 4,
      "degree": 12,
      "weighted_degree": 18,
      "top_partners": [
        { "email": "b@example.com", "shared_events": 3 },
        { "email": "c@example.com", "shared_events": 2 }
      ]
    }
  ],
  "visible_customers": 42
}
```

O endpoint retorna os clientes que têm mais conexões com outros clientes
baseadas na participação conjunta em eventos históricos.
