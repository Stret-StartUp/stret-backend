import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Optional


@dataclass
class EventFeatures:
    description: str = ""
    category: Optional[str] = None
    price: Optional[float] = None
    location: Optional[str] = None
    size: Optional[str] = None
    vibe: Optional[str] = None
    audience_type: Optional[str] = None
    colleges: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    artists: list[str] = field(default_factory=list)
    brands: list[str] = field(default_factory=list)
    idade_min: int = 18
    idade_max: int = 30
    is_universitario: bool = False
    is_open_bar: bool = False

    @property
    def keywords(self) -> list[str]:
        values = [
            self.category,
            self.location,
            self.size,
            self.vibe,
            self.audience_type,
            *self.colleges,
            *self.genres,
            *self.themes,
            *self.artists,
            *self.brands,
        ]
        return _unique_terms(values)


_GENRE_KEYWORDS = {
    "funk": "funk",
    "eletron": "eletronico",
    "sertanejo": "sertanejo",
    "pagode": "pagode",
    "axe": "axe",
    "trap": "trap",
    "rap": "rap",
    "hip hop": "hip hop",
    "rock": "rock",
    "pop": "pop",
    "samba": "samba",
}

_VIBE_KEYWORDS = {
    "premium": "premium",
    "vip": "premium",
    "camarote": "premium",
    "open bar": "premium",
    "alternativo": "alternativo",
    "underground": "alternativo",
    "universit": "universitario",
    "corporativo": "corporativo",
    "palestra": "corporativo",
    "sujeira": "sujeira",
    "bagunca": "sujeira",
}

_AUDIENCE_KEYWORDS = {
    "universit": "universitario",
    "faculdade": "universitario",
    "corporativo": "corporativo",
    "empresa": "corporativo",
    "executivo": "corporativo",
}


def build_event_features(
    *,
    description: Optional[str] = None,
    category: Optional[str] = None,
    price: Optional[float] = None,
    location: Optional[str] = None,
    size: Optional[str] = None,
    vibe: Optional[str] = None,
    audience_type: Optional[str] = None,
    colleges: Optional[str | Iterable[str]] = None,
    genres: Optional[str | Iterable[str]] = None,
    themes: Optional[str | Iterable[str]] = None,
    artists: Optional[str | Iterable[str]] = None,
    brands: Optional[str | Iterable[str]] = None,
) -> EventFeatures:
    features = parse_event(description or "")

    features.description = _clean_text(description) or ""
    features.category = _clean_text(category) or features.category
    features.price = price if price is not None else features.price
    features.location = _clean_text(location) or features.location
    features.size = _clean_text(size) or features.size
    features.vibe = _clean_text(vibe) or features.vibe
    features.audience_type = _clean_text(audience_type) or features.audience_type
    features.colleges = _merge_terms(features.colleges, colleges)
    features.genres = _merge_terms(features.genres, genres)
    features.themes = _merge_terms(features.themes, themes)
    features.artists = _merge_terms(features.artists, artists)
    features.brands = _merge_terms(features.brands, brands)

    _apply_derived_flags(features)
    return features


def parse_event(description: str) -> EventFeatures:
    text = _normalize(description)
    features = EventFeatures(description=description or "")

    if not text:
        return features

    if "open bar" in text:
        features.is_open_bar = True

    price_match = re.search(r"(?:r\$|rs)?\s*(\d{2,5})(?:[,.]\d{1,2})?", text)
    if price_match:
        features.price = float(price_match.group(1))

    for keyword, genre in _GENRE_KEYWORDS.items():
        if keyword in text:
            features.genres.append(genre)

    for keyword, vibe in _VIBE_KEYWORDS.items():
        if keyword in text and features.vibe is None:
            features.vibe = vibe

    for keyword, audience in _AUDIENCE_KEYWORDS.items():
        if keyword in text and features.audience_type is None:
            features.audience_type = audience

    _apply_derived_flags(features)
    return features


def serialize_event_features(features: EventFeatures) -> str:
    payload = asdict(features)
    payload["version"] = 1
    return json.dumps(payload, ensure_ascii=False)


def deserialize_event_features(value: str) -> EventFeatures:
    if not value:
        return EventFeatures()

    try:
        payload: dict[str, Any] = json.loads(value)
    except json.JSONDecodeError:
        return parse_event(value)

    payload.pop("version", None)
    allowed_keys = set(EventFeatures.__dataclass_fields__.keys())
    filtered = {key: payload.get(key) for key in allowed_keys if key in payload}
    features = EventFeatures(**filtered)
    _apply_derived_flags(features)
    return features


def event_features_to_text(features: EventFeatures) -> str:
    parts = [
        features.description,
        features.category,
        features.location,
        features.size,
        features.vibe,
        features.audience_type,
        ", ".join(features.colleges),
        ", ".join(features.genres),
        ", ".join(features.themes),
        ", ".join(features.artists),
        ", ".join(features.brands),
    ]
    if features.price is not None:
        parts.append(f"R${features.price:.2f}")
    return " ".join(part for part in parts if part)


def has_event_scope(features: EventFeatures) -> bool:
    return bool(event_features_to_text(features).strip())


def _apply_derived_flags(features: EventFeatures) -> None:
    text = _normalize(event_features_to_text(features))

    features.is_universitario = (
        features.audience_type == "universitario"
        or features.vibe == "universitario"
        or "universit" in text
        or bool(features.colleges)
    )
    features.is_open_bar = features.is_open_bar or "open bar" in text

    if features.is_universitario:
        features.idade_max = min(features.idade_max, 25)


def _merge_terms(current: list[str], value: Optional[str | Iterable[str]]) -> list[str]:
    return _unique_terms([*current, *_split_terms(value)])


def _split_terms(value: Optional[str | Iterable[str]]) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        raw_terms = re.split(r"[,;\n|]+", value)
    else:
        raw_terms = list(value)

    return _unique_terms(raw_terms)


def _unique_terms(values: Iterable[Any]) -> list[str]:
    terms = []
    seen = set()

    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue

        normalized = _normalize(cleaned)
        if normalized in seen:
            continue

        seen.add(normalized)
        terms.append(cleaned)

    return terms


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char))
