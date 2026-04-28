def parse_event(description: str):
    description = description.lower()

    features = {
        "idade_min": 18,
        "idade_max": 30,
        "interesses": []
    }

    if "universit" in description:
        features["idade_max"] = 25

    if "funk" in description:
        features["interesses"].append("funk")

    if "eletron" in description:
        features["interesses"].append("eletronico")

    if "open bar" in description:
        features["interesses"].append("open_bar")

    return features