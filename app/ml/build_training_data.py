import argparse
import asyncio
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from app.db.session import get_engine, get_session_factory
from app.models.customer import Customer
from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.services.analytics.scoring_service import score_clients
from app.services.ingestion.parser_service import (
    EventFeatures,
    deserialize_event_features,
    event_features_to_text,
)


DEFAULT_OUTPUT = Path(__file__).resolve().parent / "data" / "training_dataset.csv"
FEATURE_COLUMNS = [
    "affinity_score",
    "ticket_score",
    "age_score",
    "purchase_timing_score",
    "vibe_score",
    "frequency_score",
    "score",
]


@dataclass
class EventBundle:
    event: Event
    features: EventFeatures


@dataclass
class BuildSummary:
    events_seen: int = 0
    events_used: int = 0
    positive_rows: int = 0
    negative_rows: int = 0
    skipped_targets_without_history: int = 0
    skipped_positive_buyers_without_history: int = 0

    @property
    def total_rows(self) -> int:
        return self.positive_rows + self.negative_rows


async def build_training_dataset(
    output_path: Path = DEFAULT_OUTPUT,
    client_id: Optional[str] = None,
    negative_ratio: int = 3,
    include_all_negatives: bool = False,
    random_seed: int = 42,
) -> BuildSummary:
    session_factory = get_session_factory()
    rng = random.Random(random_seed)

    async with session_factory() as db:
        events = await EventRepository(db).list_with_customers(client_id=client_id)

    bundles = [
        EventBundle(event=event, features=deserialize_event_features(event.description))
        for event in events
    ]

    rows, summary = build_training_rows(
        bundles=bundles,
        negative_ratio=negative_ratio,
        include_all_negatives=include_all_negatives,
        rng=rng,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_path, index=False)

    await get_engine().dispose()
    return summary


def build_training_rows(
    bundles: list[EventBundle],
    negative_ratio: int,
    include_all_negatives: bool,
    rng: random.Random,
) -> tuple[list[dict], BuildSummary]:
    rows = []
    summary = BuildSummary(events_seen=len(bundles))
    bundles_by_client = _group_by_client(bundles)

    for client_events in bundles_by_client.values():
        for target_bundle in client_events:
            history_bundles = [
                bundle for bundle in client_events
                if bundle.event.id != target_bundle.event.id
            ]

            if not history_bundles:
                summary.skipped_targets_without_history += 1
                continue

            history_df = _build_candidate_history_df(history_bundles)
            if history_df.empty:
                summary.skipped_targets_without_history += 1
                continue

            target_buyers = {
                _normalize_email(customer.email)
                for customer in target_bundle.event.customers
                if customer.email
            }

            if not target_buyers:
                continue

            scored = score_clients(
                history_df,
                [bundle.features for bundle in history_bundles],
                target_bundle.features,
            )

            positive_candidates = scored[
                scored["email_normalized"].isin(target_buyers)
            ].copy()
            negative_candidates = scored[
                ~scored["email_normalized"].isin(target_buyers)
            ].copy()

            summary.skipped_positive_buyers_without_history += max(
                len(target_buyers) - len(positive_candidates),
                0,
            )

            if positive_candidates.empty:
                continue

            if include_all_negatives:
                sampled_negatives = negative_candidates
            else:
                negative_limit = len(positive_candidates) * max(negative_ratio, 0)
                sampled_negatives = _sample_rows(negative_candidates, negative_limit, rng)

            for _, row in positive_candidates.iterrows():
                rows.append(_dataset_row(row, target_bundle, label=1))

            for _, row in sampled_negatives.iterrows():
                rows.append(_dataset_row(row, target_bundle, label=0))

            summary.events_used += 1
            summary.positive_rows += len(positive_candidates)
            summary.negative_rows += len(sampled_negatives)

    return rows, summary


def _build_candidate_history_df(history_bundles: list[EventBundle]) -> pd.DataFrame:
    records_by_email: dict[str, list[dict]] = defaultdict(list)

    for bundle in history_bundles:
        for customer in bundle.event.customers:
            if not customer.email:
                continue
            records_by_email[_normalize_email(customer.email)].append(
                _customer_history_record(customer, bundle)
            )

    records = [
        _aggregate_customer_history(email, records)
        for email, records in records_by_email.items()
    ]

    return pd.DataFrame(records)


def _customer_history_record(customer: Customer, bundle: EventBundle) -> dict:
    features = bundle.features
    return {
        "email": customer.email,
        "email_normalized": _normalize_email(customer.email),
        "idade": customer.idade,
        "cidade": customer.cidade,
        "faculdade": customer.faculdade,
        "eventos_passados": customer.eventos_passados or [],
        "valor_medio": customer.valor_medio,
        "freq_compra": customer.freq_compra,
        "history_event_ids": [bundle.event.id],
        "history_event_count": 1,
        "historical_event_description": [event_features_to_text(features)],
        "historical_event_category": [features.category],
        "historical_event_price": [features.price],
        "historical_event_location": [features.location],
        "historical_event_size": [features.size],
        "historical_event_vibe": [features.vibe],
        "historical_event_audience_type": [features.audience_type],
        "historical_event_colleges": features.colleges,
        "historical_event_genres": features.genres,
        "historical_event_themes": features.themes,
        "historical_event_artists": features.artists,
        "historical_event_brands": features.brands,
    }


def _aggregate_customer_history(email: str, records: list[dict]) -> dict:
    return {
        "email": _first_non_empty(record.get("email") for record in records),
        "email_normalized": email,
        "idade": _first_non_empty(record.get("idade") for record in records),
        "cidade": _most_common_text(record.get("cidade") for record in records),
        "faculdade": _most_common_text(record.get("faculdade") for record in records),
        "eventos_passados": _flatten(record.get("eventos_passados") for record in records),
        "valor_medio": _mean(record.get("valor_medio") for record in records),
        "freq_compra": _sum(record.get("freq_compra") for record in records),
        "history_event_ids": _flatten(record.get("history_event_ids") for record in records),
        "history_event_count": len(records),
        "historical_event_description": " ".join(
            _flatten(record.get("historical_event_description") for record in records)
        ),
        "historical_event_category": " ".join(
            _flatten(record.get("historical_event_category") for record in records)
        ),
        "historical_event_price": _mean(
            _flatten(record.get("historical_event_price") for record in records)
        ),
        "historical_event_location": " ".join(
            _flatten(record.get("historical_event_location") for record in records)
        ),
        "historical_event_size": " ".join(
            _flatten(record.get("historical_event_size") for record in records)
        ),
        "historical_event_vibe": " ".join(
            _flatten(record.get("historical_event_vibe") for record in records)
        ),
        "historical_event_audience_type": " ".join(
            _flatten(record.get("historical_event_audience_type") for record in records)
        ),
        "historical_event_colleges": _flatten(
            record.get("historical_event_colleges") for record in records
        ),
        "historical_event_genres": _flatten(
            record.get("historical_event_genres") for record in records
        ),
        "historical_event_themes": _flatten(
            record.get("historical_event_themes") for record in records
        ),
        "historical_event_artists": _flatten(
            record.get("historical_event_artists") for record in records
        ),
        "historical_event_brands": _flatten(
            record.get("historical_event_brands") for record in records
        ),
    }


def _dataset_row(row: pd.Series, target_bundle: EventBundle, label: int) -> dict:
    target = target_bundle.features
    return {
        "label": label,
        "client_id": target_bundle.event.client_id,
        "target_event_id": target_bundle.event.id,
        "customer_email": row.get("email"),
        "history_event_count": row.get("history_event_count"),
        "history_event_ids": "|".join(str(value) for value in row.get("history_event_ids", [])),
        "target_category": target.category,
        "target_price": target.price,
        "target_location": target.location,
        "target_size": target.size,
        "target_vibe": target.vibe,
        "target_audience_type": target.audience_type,
        "target_colleges": "|".join(target.colleges),
        "target_genres": "|".join(target.genres),
        "target_themes": "|".join(target.themes),
        "target_artists": "|".join(target.artists),
        "target_brands": "|".join(target.brands),
        "customer_age": row.get("idade"),
        "customer_city": row.get("cidade"),
        "customer_college": row.get("faculdade"),
        "customer_avg_ticket": row.get("valor_medio"),
        "customer_purchase_frequency": row.get("freq_compra"),
        **{column: row.get(column) for column in FEATURE_COLUMNS},
    }


def _group_by_client(bundles: list[EventBundle]) -> dict[str, list[EventBundle]]:
    grouped: dict[str, list[EventBundle]] = defaultdict(list)

    for bundle in bundles:
        grouped[bundle.event.client_id].append(bundle)

    return grouped


def _sample_rows(df: pd.DataFrame, limit: int, rng: random.Random) -> pd.DataFrame:
    if limit <= 0 or df.empty:
        return df.head(0)

    if len(df) <= limit:
        return df

    sampled_indexes = rng.sample(list(df.index), limit)
    return df.loc[sampled_indexes]


def _normalize_email(email: str) -> str:
    return str(email).strip().lower()


def _first_non_empty(values: Iterable) -> Optional[object]:
    for value in values:
        if not _is_empty(value):
            return value
    return None


def _most_common_text(values: Iterable) -> Optional[str]:
    counts = defaultdict(int)

    for value in values:
        if _is_empty(value):
            continue
        counts[str(value)] += 1

    if not counts:
        return None

    return max(counts.items(), key=lambda item: item[1])[0]


def _flatten(values: Iterable) -> list:
    flattened = []

    for value in values:
        if _is_empty(value):
            continue
        if isinstance(value, list):
            flattened.extend(item for item in value if not _is_empty(item))
        elif isinstance(value, tuple):
            flattened.extend(item for item in value if not _is_empty(item))
        else:
            flattened.append(value)

    return flattened


def _mean(values: Iterable) -> Optional[float]:
    valid_values = [float(value) for value in values if not _is_empty(value)]
    if not valid_values:
        return None
    return sum(valid_values) / len(valid_values)


def _sum(values: Iterable) -> Optional[int]:
    valid_values = [int(value) for value in values if not _is_empty(value)]
    if not valid_values:
        return None
    return sum(valid_values)


def _is_empty(value) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the EventRank ML training dataset from historical uploads."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--client-id",
        default=None,
        help="Optional client_id filter.",
    )
    parser.add_argument(
        "--negative-ratio",
        type=int,
        default=3,
        help="Number of negative samples per positive sample. Ignored with --all-negatives.",
    )
    parser.add_argument(
        "--all-negatives",
        action="store_true",
        help="Use every eligible negative sample instead of sampling by ratio.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for negative sampling.",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    summary = await build_training_dataset(
        output_path=args.output,
        client_id=args.client_id,
        negative_ratio=args.negative_ratio,
        include_all_negatives=args.all_negatives,
        random_seed=args.seed,
    )

    print(f"Dataset salvo em: {args.output}")
    print(f"Eventos encontrados: {summary.events_seen}")
    print(f"Eventos usados: {summary.events_used}")
    print(f"Linhas positivas: {summary.positive_rows}")
    print(f"Linhas negativas: {summary.negative_rows}")
    print(f"Total de linhas: {summary.total_rows}")
    print(
        "Compradores positivos sem historico previo em outros eventos: "
        f"{summary.skipped_positive_buyers_without_history}"
    )


if __name__ == "__main__":
    asyncio.run(_main())
