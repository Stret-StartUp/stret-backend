"""
Testes para os serviços de Intelligent Weighting e Weight Optimizer.
"""

import os
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app.services.analytics.intelligent_weighting import (
    IntelligentWeights,
    IntelligentWeightingService,
)
from app.services.analytics.weight_optimizer import WeightOptimizer


class TestIntelligentWeights:
    """Testes para a classe IntelligentWeights."""

    def test_creation_with_defaults(self):
        """Testa criação com valores padrão."""
        weights = IntelligentWeights()
        assert weights.event_similarity_weight == 0.25
        assert weights.affinity_weight == 0.25
        assert weights.validate()

    def test_to_dict(self):
        """Testa conversão para dicionário."""
        weights = IntelligentWeights(event_similarity_weight=0.5)
        d = weights.to_dict()
        assert d["event_similarity_weight"] == 0.5
        assert "affinity_weight" in d

    def test_to_json(self):
        """Testa conversão para JSON."""
        weights = IntelligentWeights()
        json_str = weights.to_json()
        assert isinstance(json_str, str)
        assert "event_similarity_weight" in json_str

    def test_from_json(self):
        """Testa criação a partir de JSON."""
        weights = IntelligentWeights(event_similarity_weight=0.5)
        json_str = weights.to_json()
        loaded = IntelligentWeights.from_json(json_str)
        assert loaded.event_similarity_weight == 0.5

    def test_validate_negative_weight(self):
        """Testa validação com peso negativo."""
        weights = IntelligentWeights(event_similarity_weight=-0.5)
        assert not weights.validate()

    def test_validate_all_positive(self):
        """Testa validação com todos positivos."""
        weights = IntelligentWeights()
        assert weights.validate()


class TestIntelligentWeightingService:
    """Testes para o serviço de ponderação inteligente."""

    def test_initialization(self):
        """Testa inicialização do serviço."""
        service = IntelligentWeightingService()
        assert service.weights is not None
        assert isinstance(service.weights, IntelligentWeights)

    def test_score_customer_basic(self):
        """Testa scoring básico de cliente."""
        service = IntelligentWeightingService()

        features = {
            "event_similarity_score": 0.8,
            "affinity_score": 0.7,
            "ticket_score": 0.6,
            "age_score": 0.5,
            "purchase_timing_score": 0.4,
            "vibe_score": 0.3,
            "frequency_score": 0.2,
        }

        score = service.score_customer(features)
        assert isinstance(score, float)
        assert score >= 0
        assert score <= 100

    def test_score_customer_all_zeros(self):
        """Testa scoring com features zeradas."""
        service = IntelligentWeightingService()

        features = {
            "event_similarity_score": 0.0,
            "affinity_score": 0.0,
            "ticket_score": 0.0,
            "age_score": 0.0,
            "purchase_timing_score": 0.0,
            "vibe_score": 0.0,
            "frequency_score": 0.0,
        }

        score = service.score_customer(features)
        assert score == 0.0

    def test_score_customer_missing_feature(self):
        """Testa scoring com feature faltando."""
        service = IntelligentWeightingService()

        features = {
            "event_similarity_score": 0.8,
            "affinity_score": 0.7,
            # Faltando outras features
        }

        score = service.score_customer(features)
        assert isinstance(score, float)
        assert score >= 0

    def test_batch_score(self):
        """Testa scoring em lote."""
        service = IntelligentWeightingService()

        features_list = [
            {
                "event_similarity_score": 0.8,
                "affinity_score": 0.7,
                "ticket_score": 0.6,
                "age_score": 0.5,
                "purchase_timing_score": 0.4,
                "vibe_score": 0.3,
                "frequency_score": 0.2,
            },
            {
                "event_similarity_score": 0.5,
                "affinity_score": 0.5,
                "ticket_score": 0.5,
                "age_score": 0.5,
                "purchase_timing_score": 0.5,
                "vibe_score": 0.5,
                "frequency_score": 0.5,
            },
        ]

        scores = service.batch_score(features_list)
        assert len(scores) == 2
        assert all(isinstance(s, float) for s in scores)
        assert scores[0] > scores[1]  # Primeiro deve ter score maior

    def test_get_weights(self):
        """Testa obtenção de pesos atuais."""
        service = IntelligentWeightingService()
        weights = service.get_weights()
        assert isinstance(weights, dict)
        assert "event_similarity_weight" in weights

    def test_update_weights_valid(self):
        """Testa atualização com pesos válidos."""
        service = IntelligentWeightingService()

        new_weights = {
            "event_similarity_weight": 0.3,
            "affinity_weight": 0.3,
            "ticket_weight": 0.2,
            "age_weight": 0.1,
            "purchase_timing_weight": 0.05,
            "vibe_weight": 0.03,
            "frequency_weight": 0.02,
        }

        success = service.update_weights(new_weights)
        assert success
        assert service.weights.event_similarity_weight == 0.3

    def test_update_weights_invalid(self):
        """Testa atualização com pesos inválidos."""
        service = IntelligentWeightingService()

        new_weights = {
            "event_similarity_weight": -0.5,  # Negativo!
            "affinity_weight": 0.5,
            "ticket_weight": 0.0,
            "age_weight": 0.0,
            "purchase_timing_weight": 0.0,
            "vibe_weight": 0.0,
            "frequency_weight": 0.0,
        }

        success = service.update_weights(new_weights)
        assert not success

    def test_update_weights_all_zero(self):
        """Testa atualização com pesos todos zero."""
        service = IntelligentWeightingService()

        new_weights = {
            "event_similarity_weight": 0.0,
            "affinity_weight": 0.0,
            "ticket_weight": 0.0,
            "age_weight": 0.0,
            "purchase_timing_weight": 0.0,
            "vibe_weight": 0.0,
            "frequency_weight": 0.0,
        }

        success = service.update_weights(new_weights)
        assert not success

    def test_update_weights_normalizes(self):
        """Testa que pesos são normalizados para soma igual a 1."""
        service = IntelligentWeightingService()

        new_weights = {
            "event_similarity_weight": 0.3,
            "affinity_weight": 0.3,
            "ticket_weight": 0.2,
            "age_weight": 0.1,
            "purchase_timing_weight": 0.05,
            "vibe_weight": 0.03,
            "frequency_weight": 0.02,
        }

        success = service.update_weights(new_weights)
        assert success

        weights = service.get_weights()
        assert pytest.approx(sum(weights.values()), rel=1e-6) == 1.0

    def test_reset_to_defaults(self):
        """Testa reset para valores padrão."""
        service = IntelligentWeightingService()

        # Mudar pesos
        new_weights = {
            "event_similarity_weight": 0.9,
            "affinity_weight": 0.1,
            "ticket_weight": 0.0,
            "age_weight": 0.0,
            "purchase_timing_weight": 0.0,
            "vibe_weight": 0.0,
            "frequency_weight": 0.0,
        }
        service.update_weights(new_weights)

        # Reset
        service.reset_to_defaults()

        weights = service.get_weights()
        # Deve estar próximo dos defaults (0.25 para event_similarity)
        assert weights["event_similarity_weight"] > 0.2


class TestWeightOptimizer:
    """Testes para o otimizador de pesos."""

    def test_initialization(self):
        """Testa inicialização do otimizador."""
        optimizer = WeightOptimizer()
        assert optimizer.FEATURE_NAMES
        assert len(optimizer.WEIGHT_NAMES) == len(optimizer.FEATURE_NAMES)

    def test_optimize_empty_data(self):
        """Testa otimização com dados vazios."""
        optimizer = WeightOptimizer()
        empty_df = pd.DataFrame()

        result = optimizer.optimize(empty_df)
        assert not result.success
        assert "vazio" in result.message.lower()

    def test_optimize_single_label(self):
        """Testa otimização com apenas um valor de label."""
        optimizer = WeightOptimizer()

        # Todos compram (label = 1)
        df = pd.DataFrame(
            {
                "event_similarity_score": [0.8, 0.7, 0.6],
                "affinity_score": [0.7, 0.6, 0.5],
                "ticket_score": [0.5, 0.5, 0.5],
                "age_score": [0.5, 0.5, 0.5],
                "purchase_timing_score": [0.5, 0.5, 0.5],
                "vibe_score": [0.5, 0.5, 0.5],
                "frequency_score": [0.5, 0.5, 0.5],
                "bought": [1, 1, 1],
            }
        )

        result = optimizer.optimize(df)
        assert not result.success

    def test_optimize_synthetic_data(self):
        """Testa otimização com dados sintéticos."""
        optimizer = WeightOptimizer()

        # Criar dados onde event_similarity é o preditor mais importante
        np.random.seed(42)
        n_samples = 100

        event_sim = np.random.rand(n_samples)
        affinity = np.random.rand(n_samples)
        ticket = np.random.rand(n_samples)
        age = np.random.rand(n_samples)
        timing = np.random.rand(n_samples)
        vibe = np.random.rand(n_samples)
        frequency = np.random.rand(n_samples)

        # Label baseado em event_similarity (forte) + ruído
        bought = (event_sim > 0.5).astype(int) + np.random.binomial(1, 0.1, n_samples)
        bought = (bought > 0).astype(int)

        df = pd.DataFrame(
            {
                "event_similarity_score": event_sim,
                "affinity_score": affinity,
                "ticket_score": ticket,
                "age_score": age,
                "purchase_timing_score": timing,
                "vibe_score": vibe,
                "frequency_score": frequency,
                "bought": bought,
            }
        )

        # Pesos iniciais (todos iguais)
        initial_weights = {
            "event_similarity_weight": 0.143,
            "affinity_weight": 0.143,
            "ticket_weight": 0.143,
            "age_weight": 0.143,
            "purchase_timing_weight": 0.143,
            "vibe_weight": 0.143,
            "frequency_weight": 0.143,
        }

        result = optimizer.optimize(df, initial_weights=initial_weights, max_iterations=500)

        # Deve otimizar (ou pelo menos não falhar)
        assert result.old_weights
        assert result.new_weights
        assert "event_similarity_weight" in result.new_weights

    def test_cross_validate_insufficient_data(self):
        """Testa CV com dados insuficientes."""
        optimizer = WeightOptimizer()

        df = pd.DataFrame(
            {
                "event_similarity_score": [0.8, 0.6],
                "affinity_score": [0.7, 0.5],
                "ticket_score": [0.5, 0.4],
                "age_score": [0.5, 0.5],
                "purchase_timing_score": [0.5, 0.5],
                "vibe_score": [0.5, 0.5],
                "frequency_score": [0.5, 0.5],
                "bought": [1, 0],
            }
        )

        result = optimizer.cross_validate(df, n_splits=5)
        assert not result.get("success", False)

    def test_cross_validate_sufficient_data(self):
        """Testa CV com dados suficientes."""
        optimizer = WeightOptimizer()

        np.random.seed(42)
        n_samples = 100

        event_sim = np.random.rand(n_samples)
        bought = (event_sim > 0.5).astype(int)

        df = pd.DataFrame(
            {
                "event_similarity_score": event_sim,
                "affinity_score": np.random.rand(n_samples),
                "ticket_score": np.random.rand(n_samples),
                "age_score": np.random.rand(n_samples),
                "purchase_timing_score": np.random.rand(n_samples),
                "vibe_score": np.random.rand(n_samples),
                "frequency_score": np.random.rand(n_samples),
                "bought": bought,
            }
        )

        result = optimizer.cross_validate(df, n_splits=5)
        assert result.get("success", False)
        if result.get("success"):
            assert "mean_accuracy" in result
            assert result["mean_accuracy"] >= 0.5  # Deve estar acima do aleatório
