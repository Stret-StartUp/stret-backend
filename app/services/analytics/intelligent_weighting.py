"""
Serviço de ponderação inteligente de scoring.

Responsabilidades:
- Carregar pesos aprendíveis ou usar defaults
- Calcular score ponderado com features individuais
- Permitir atualizar pesos com base em histórico de compras
"""

import json
import os
from dataclasses import asdict, dataclass
from typing import Dict, Optional

from app.core.config import settings


@dataclass
class IntelligentWeights:
    """Pesos aprendíveis para scoring."""

    event_similarity_weight: float = 0.25
    affinity_weight: float = 0.25
    ticket_weight: float = 0.15
    age_weight: float = 0.10
    purchase_timing_weight: float = 0.10
    vibe_weight: float = 0.08
    frequency_weight: float = 0.07

    def to_dict(self) -> Dict[str, float]:
        """Converte para dicionário."""
        return asdict(self)

    def to_json(self) -> str:
        """Converte para JSON."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "IntelligentWeights":
        """Cria a partir de dicionário."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "IntelligentWeights":
        """Cria a partir de JSON."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def validate(self) -> bool:
        """Valida que todos os pesos são não-negativos e somam mais que zero."""
        weights = asdict(self)
        for weight in weights.values():
            if weight < 0:
                return False
        return sum(weights.values()) > 0


class IntelligentWeightingService:
    """
    Serviço de ponderação inteligente.

    Mantém pesos aprendíveis que podem ser otimizados baseado em
    histórico de compras reais.
    """

    WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "weights.json")

    def __init__(self):
        """Inicializa o serviço carregando pesos ou criando defaults."""
        self.weights = self._load_weights()

    def _load_weights(self) -> IntelligentWeights:
        """Carrega pesos do arquivo ou retorna defaults."""
        if os.path.exists(self.WEIGHTS_PATH):
            try:
                with open(self.WEIGHTS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    weights = IntelligentWeights.from_dict(data)
                    if weights.validate():
                        return weights
            except Exception:
                pass

        # Fallback para defaults do settings
        return IntelligentWeights(
            event_similarity_weight=settings.EVENT_SIMILARITY_WEIGHT,
            affinity_weight=settings.AFFINITY_WEIGHT,
            ticket_weight=settings.TICKET_WEIGHT,
            age_weight=settings.AGE_WEIGHT,
            purchase_timing_weight=settings.PURCHASE_TIMING_WEIGHT,
            vibe_weight=settings.VIBE_WEIGHT,
            frequency_weight=settings.FREQUENCY_WEIGHT,
        )

    def _save_weights(self) -> None:
        """Salva pesos em arquivo."""
        os.makedirs(os.path.dirname(self.WEIGHTS_PATH), exist_ok=True)
        with open(self.WEIGHTS_PATH, "w", encoding="utf-8") as f:
            f.write(self.weights.to_json())

    def score_customer(self, features_dict: Dict[str, float]) -> float:
        """
        Calcula score ponderado de um cliente.

        Args:
            features_dict: Dicionário com features individuais
                Esperado conter:
                - event_similarity_score
                - affinity_score
                - ticket_score
                - age_score
                - purchase_timing_score
                - vibe_score
                - frequency_score

        Returns:
            Score ponderado (não normalizado, pode ser > 1)
        """
        weights_dict = self.weights.to_dict()
        score = 0.0

        for feature_name, weight in weights_dict.items():
            # Converte snake_case do peso para snake_case da feature
            # event_similarity_weight -> event_similarity_score
            feature_key = feature_name.replace("_weight", "_score")

            if feature_key in features_dict:
                score += features_dict[feature_key] * weight

        return min(score, 100.0)  # Cap em 100 para segurança

    def batch_score(self, features_list: list[Dict[str, float]]) -> list[float]:
        """
        Calcula scores para múltiplos clientes.

        Args:
            features_list: Lista de dicionários com features

        Returns:
            Lista de scores
        """
        return [self.score_customer(features) for features in features_list]

    def update_weights(self, new_weights: Dict[str, float]) -> bool:
        """
        Atualiza pesos com valores novos (otimizados).

        Args:
            new_weights: Dicionário com novos pesos

        Returns:
            True se bem-sucedido, False caso contrário
        """
        try:
            updated = IntelligentWeights.from_dict(new_weights)

            if not updated.validate():
                return False

            normalized = {k: v / sum(updated.to_dict().values()) for k, v in updated.to_dict().items()}
            self.weights = IntelligentWeights.from_dict(normalized)
            self._save_weights()
            return True

        except Exception:
            return False

    def get_weights(self) -> Dict[str, float]:
        """Retorna pesos atuais."""
        return self.weights.to_dict()

    def reset_to_defaults(self) -> None:
        """Reseta pesos para defaults do config."""
        self.weights = IntelligentWeights(
            event_similarity_weight=settings.EVENT_SIMILARITY_WEIGHT,
            affinity_weight=settings.AFFINITY_WEIGHT,
            ticket_weight=settings.TICKET_WEIGHT,
            age_weight=settings.AGE_WEIGHT,
            purchase_timing_weight=settings.PURCHASE_TIMING_WEIGHT,
            vibe_weight=settings.VIBE_WEIGHT,
            frequency_weight=settings.FREQUENCY_WEIGHT,
        )
        self._save_weights()
