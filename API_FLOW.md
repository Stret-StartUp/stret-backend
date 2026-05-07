# API flow

O fluxo principal usa historico acumulado:

1. `POST /api/v1/upload`
   - salva um evento historico e os consumidores do Excel no MySQL.
   - pode ser chamado varias vezes para o mesmo `client_id`.

2. `POST /api/v1/query`
   - recebe o escopo do evento alvo.
   - compara esse evento com todo o historico salvo para o `client_id`.
   - retorna um Excel com o ranking.

3. `POST /api/v1/profile`
   - recebe o escopo do evento alvo.
   - analisa o perfil de consumidor a partir do historico salvo.

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
