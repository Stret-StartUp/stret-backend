def get_lote_score(eventos_passados):
    score = 0

    for evento in eventos_passados:
        evento = evento.lower()

        if "promocional" in evento or "1º" in evento or "1o" in evento:
            score += 1.0
        elif "2º" in evento or "2o" in evento:
            score += 0.7
        elif "3º" in evento or "3o" in evento:
            score += 0.5
        else:
            score += 0.3

    return score / len(eventos_passados) if eventos_passados else 0


def match_event_similarity(past_event_desc, current_event_features):
    score = 0
    past_event_desc = past_event_desc.lower()

    for interesse in current_event_features["interesses"]:
        if interesse in past_event_desc:
            score += 1

    return score / len(current_event_features["interesses"]) if current_event_features["interesses"] else 0


def score_clients(df, past_event_desc, current_event_features):
    def calculate_score(row):
        score = 0

        score += match_event_similarity(past_event_desc, current_event_features) * 0.4

        if row["idade"]:
            if current_event_features["idade_min"] <= row["idade"] <= current_event_features["idade_max"]:
                score += 0.2

        lote_score = get_lote_score(row["eventos_passados"])
        score += lote_score * 0.3

        if row["freq_compra"]:
            score += min(row["freq_compra"] * 0.05, 0.1)

        return score

    df["score"] = df.apply(calculate_score, axis=1)
    return df.sort_values(by="score", ascending=False)