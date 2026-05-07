import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.build_training_data import DEFAULT_OUTPUT as DEFAULT_DATASET


MODEL_DIR = Path(__file__).resolve().parent / "models"
REPORT_DIR = Path(__file__).resolve().parent / "reports"
DEFAULT_MODEL_OUTPUT = MODEL_DIR / "baseline_model.joblib"
DEFAULT_REPORT_OUTPUT = REPORT_DIR / "baseline_metrics.json"

FEATURE_COLUMNS = [
    "affinity_score",
    "ticket_score",
    "age_score",
    "purchase_timing_score",
    "vibe_score",
    "frequency_score",
    "score",
]
LABEL_COLUMN = "label"
GROUP_COLUMN = "target_event_id"


@dataclass
class TrainingResult:
    best_model_name: str
    metrics: dict
    model_output: Path
    report_output: Path


def train_baseline_models(
    dataset_path: Path = DEFAULT_DATASET,
    model_output: Path = DEFAULT_MODEL_OUTPUT,
    report_output: Path = DEFAULT_REPORT_OUTPUT,
    test_size: float = 0.30,
    random_seed: int = 42,
    precision_at: tuple[int, ...] = (50, 100),
) -> TrainingResult:
    df = pd.read_csv(dataset_path)
    _validate_dataset(df)

    train_df, test_df = _split_by_event(df, test_size=test_size, random_seed=random_seed)
    models = _build_models(random_seed)

    metrics_by_model = {}
    fitted_models = {}

    for model_name, model in models.items():
        model.fit(train_df[FEATURE_COLUMNS], train_df[LABEL_COLUMN])
        predictions = model.predict_proba(test_df[FEATURE_COLUMNS])[:, 1]

        metrics_by_model[model_name] = _evaluate_predictions(
            y_true=test_df[LABEL_COLUMN],
            y_score=predictions,
            test_df=test_df,
            precision_at=precision_at,
        )
        fitted_models[model_name] = model

    best_model_name = _select_best_model(metrics_by_model)
    best_model = fitted_models[best_model_name]

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "feature_columns": FEATURE_COLUMNS,
        "label_column": LABEL_COLUMN,
        "group_column": GROUP_COLUMN,
        "split": {
            "strategy": "GroupShuffleSplit by target_event_id",
            "test_size": test_size,
            "random_seed": random_seed,
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "train_events": sorted(_to_builtin_list(train_df[GROUP_COLUMN].unique())),
            "test_events": sorted(_to_builtin_list(test_df[GROUP_COLUMN].unique())),
            "train_label_counts": _label_counts(train_df),
            "test_label_counts": _label_counts(test_df),
        },
        "models": metrics_by_model,
        "best_model": best_model_name,
    }

    artifact = {
        "model_name": best_model_name,
        "model": best_model,
        "feature_columns": FEATURE_COLUMNS,
        "metrics": metrics_by_model[best_model_name],
        "training_report": report,
    }

    model_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_output)
    report_output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return TrainingResult(
        best_model_name=best_model_name,
        metrics=metrics_by_model[best_model_name],
        model_output=model_output,
        report_output=report_output,
    )


def _validate_dataset(df: pd.DataFrame) -> None:
    missing_columns = [
        column for column in [*FEATURE_COLUMNS, LABEL_COLUMN, GROUP_COLUMN]
        if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(f"Dataset sem colunas obrigatorias: {missing_columns}")

    if df.empty:
        raise ValueError("Dataset vazio.")

    if df[LABEL_COLUMN].nunique() < 2:
        raise ValueError("Dataset precisa ter labels 0 e 1 para treino supervisionado.")

    if df[GROUP_COLUMN].nunique() < 2:
        raise ValueError(
            "Dataset precisa ter pelo menos 2 eventos-alvo para split por evento."
        )


def _split_by_event(
    df: pd.DataFrame,
    test_size: float,
    random_seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=test_size,
        random_state=random_seed,
    )
    train_idx, test_idx = next(
        splitter.split(df, y=df[LABEL_COLUMN], groups=df[GROUP_COLUMN])
    )
    train_df = df.iloc[train_idx].copy()
    test_df = df.iloc[test_idx].copy()

    _validate_split(train_df, test_df)
    return train_df, test_df


def _validate_split(train_df: pd.DataFrame, test_df: pd.DataFrame) -> None:
    for split_name, split_df in {"train": train_df, "test": test_df}.items():
        if split_df[LABEL_COLUMN].nunique() < 2:
            raise ValueError(
                f"Split {split_name} ficou com apenas uma classe. "
                "Adicione mais eventos historicos ou gere o dataset com mais dados."
            )


def _build_models(random_seed: int) -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=1000,
                        class_weight="balanced",
                        random_state=random_seed,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=300,
                        min_samples_leaf=10,
                        class_weight="balanced_subsample",
                        random_state=random_seed,
                        n_jobs=1,
                    ),
                ),
            ]
        ),
    }


def _evaluate_predictions(
    y_true: pd.Series,
    y_score,
    test_df: pd.DataFrame,
    precision_at: tuple[int, ...],
) -> dict:
    y_true_values = y_true.astype(int).to_numpy()

    metrics = {
        "roc_auc": _safe_metric(roc_auc_score, y_true_values, y_score),
        "average_precision": _safe_metric(average_precision_score, y_true_values, y_score),
        "log_loss": _safe_metric(log_loss, y_true_values, y_score),
    }

    ranking_metrics = {}
    scored_df = test_df[[GROUP_COLUMN, LABEL_COLUMN]].copy()
    scored_df["prediction"] = y_score

    for k in precision_at:
        ranking_metrics[f"precision_at_{k}"] = _precision_at_k(scored_df, k)
        ranking_metrics[f"recall_at_{k}"] = _recall_at_k(scored_df, k)

    metrics.update(ranking_metrics)
    return metrics


def _safe_metric(metric_fn, y_true, y_score) -> Optional[float]:
    try:
        return float(metric_fn(y_true, y_score))
    except ValueError:
        return None


def _precision_at_k(scored_df: pd.DataFrame, k: int) -> Optional[float]:
    values = []

    for _, event_df in scored_df.groupby(GROUP_COLUMN):
        top = event_df.sort_values("prediction", ascending=False).head(k)
        if top.empty:
            continue
        values.append(float(top[LABEL_COLUMN].mean()))

    return _mean(values)


def _recall_at_k(scored_df: pd.DataFrame, k: int) -> Optional[float]:
    values = []

    for _, event_df in scored_df.groupby(GROUP_COLUMN):
        total_positives = int(event_df[LABEL_COLUMN].sum())
        if total_positives <= 0:
            continue
        top = event_df.sort_values("prediction", ascending=False).head(k)
        values.append(float(top[LABEL_COLUMN].sum() / total_positives))

    return _mean(values)


def _mean(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return float(sum(values) / len(values))


def _select_best_model(metrics_by_model: dict[str, dict]) -> str:
    def sort_key(item):
        _, metrics = item
        return (
            metrics.get("roc_auc") if metrics.get("roc_auc") is not None else -1.0,
            metrics.get("average_precision")
            if metrics.get("average_precision") is not None else -1.0,
        )

    return max(metrics_by_model.items(), key=sort_key)[0]


def _label_counts(df: pd.DataFrame) -> dict[str, int]:
    return {
        str(label): int(count)
        for label, count in df[LABEL_COLUMN].value_counts().sort_index().items()
    }


def _to_builtin_list(values) -> list:
    return [int(value) if hasattr(value, "item") else value for value in values]


def _parse_precision_at(value: str) -> tuple[int, ...]:
    return tuple(
        int(item.strip())
        for item in value.split(",")
        if item.strip()
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train baseline ML models for EventRank."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help=f"Training dataset CSV. Default: {DEFAULT_DATASET}",
    )
    parser.add_argument(
        "--model-output",
        type=Path,
        default=DEFAULT_MODEL_OUTPUT,
        help=f"Model artifact output. Default: {DEFAULT_MODEL_OUTPUT}",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=DEFAULT_REPORT_OUTPUT,
        help=f"Metrics JSON output. Default: {DEFAULT_REPORT_OUTPUT}",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.30,
        help="Fraction of target events used for test.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed.",
    )
    parser.add_argument(
        "--precision-at",
        default="50,100",
        help="Comma-separated ranking cutoffs. Example: 10,50,100",
    )
    return parser.parse_args()


def _main() -> None:
    args = _parse_args()
    result = train_baseline_models(
        dataset_path=args.dataset,
        model_output=args.model_output,
        report_output=args.report_output,
        test_size=args.test_size,
        random_seed=args.seed,
        precision_at=_parse_precision_at(args.precision_at),
    )

    print(f"Melhor modelo: {result.best_model_name}")
    print(f"Modelo salvo em: {result.model_output}")
    print(f"Relatorio salvo em: {result.report_output}")
    print(json.dumps(result.metrics, indent=2))


if __name__ == "__main__":
    _main()
