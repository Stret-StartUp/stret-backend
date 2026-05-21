"""
Otimizador de pesos de scoring baseado em histórico de compras.

Responsabilidades:
- Otimizar pesos usando histórico de clientes que compraram vs não compraram
- Validar qualidade da otimização
- Gerar relatórios de melhoria
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize


@dataclass
class OptimizationResult:
    """Resultado da otimização de pesos."""

    success: bool
    old_weights: Dict[str, float]
    new_weights: Dict[str, float]
    improvement_percentage: float  # Melhoria em acurácia (%)
    accuracy_before: float
    accuracy_after: float
    iterations: int
    message: str


class WeightOptimizer:
    """
    Otimizador de pesos usando histórico de compras reais.

    Encontra os melhores pesos que maximizam a acurácia de predição
    dados clientes que compraram e não compraram.
    """

    # Nomes das features e seus correspondentes pesos
    FEATURE_NAMES = [
        "event_similarity_score",
        "affinity_score",
        "ticket_score",
        "age_score",
        "purchase_timing_score",
        "vibe_score",
        "frequency_score",
    ]

    WEIGHT_NAMES = [
        "event_similarity_weight",
        "affinity_weight",
        "ticket_weight",
        "age_weight",
        "purchase_timing_weight",
        "vibe_weight",
        "frequency_weight",
    ]

    def __init__(self):
        """Inicializa o otimizador."""
        self._call_count = 0

    def optimize(
        self,
        historical_data: pd.DataFrame,
        target_column: str = "bought",
        initial_weights: Optional[Dict[str, float]] = None,
        threshold: float = 0.5,
        max_iterations: int = 1000,
    ) -> OptimizationResult:
        """
        Otimiza pesos usando histórico de compras.

        Args:
            historical_data: DataFrame com features e label de compra
                Esperado conter colunas: event_similarity_score, affinity_score, ...
                e uma coluna target (0/1 indicando compra)
            target_column: Nome da coluna com label de compra
            initial_weights: Dicionário com pesos iniciais (optional)
            threshold: Threshold para classificação binária (default 0.5)
            max_iterations: Máximo de iterações de otimização

        Returns:
            OptimizationResult com detalhes da otimização
        """
        # Validação básica
        if historical_data.empty:
            return OptimizationResult(
                success=False,
                old_weights={},
                new_weights={},
                improvement_percentage=0.0,
                accuracy_before=0.0,
                accuracy_after=0.0,
                iterations=0,
                message="Dados históricos vazios",
            )

        # Preparar dados
        try:
            X = historical_data[self.FEATURE_NAMES].values
            y = historical_data[target_column].values

            # Validar que tem label 0 e 1
            if len(np.unique(y)) < 2:
                return OptimizationResult(
                    success=False,
                    old_weights=initial_weights or {},
                    new_weights={},
                    improvement_percentage=0.0,
                    accuracy_before=0.0,
                    accuracy_after=0.0,
                    iterations=0,
                    message="Label deve conter valores 0 e 1",
                )

        except KeyError as e:
            return OptimizationResult(
                success=False,
                old_weights=initial_weights or {},
                new_weights={},
                improvement_percentage=0.0,
                accuracy_before=0.0,
                accuracy_after=0.0,
                iterations=0,
                message=f"Coluna faltando: {e}",
            )

        # Pesos iniciais
        if initial_weights:
            x0 = np.array([initial_weights.get(name, 0.1) for name in self.WEIGHT_NAMES])
        else:
            x0 = np.ones(len(self.FEATURE_NAMES)) / len(self.FEATURE_NAMES)

        # Normalizar pesos iniciais
        x0 = x0 / np.sum(x0)

        # Calcular acurácia antes
        accuracy_before = self._calculate_accuracy(X, y, x0, threshold)

        # Função de loss a minimizar
        def loss_function(weights):
            # Garantir que pesos são não-negativos
            weights = np.abs(weights)
            if np.sum(weights) == 0:
                return 1.0  # Loss máximo

            # Normalizar
            weights = weights / np.sum(weights)

            # Erro de classificação
            predictions = (X @ weights > threshold).astype(int)
            accuracy = np.mean(predictions == y)
            return 1.0 - accuracy  # Minimizar erro = maximizar acurácia

        # Otimizar
        self._call_count = 0
        result = minimize(
            loss_function,
            x0=x0,
            method="Nelder-Mead",
            options={"maxiter": max_iterations, "xatol": 1e-4, "fatol": 1e-4},
        )

        # Extrair pesos otimizados
        optimized_weights = np.abs(result.x)
        optimized_weights = optimized_weights / np.sum(optimized_weights)

        # Calcular acurácia depois
        accuracy_after = self._calculate_accuracy(X, y, optimized_weights, threshold)

        # Montar resultado
        new_weights_dict = dict(zip(self.WEIGHT_NAMES, optimized_weights.tolist()))
        old_weights_dict = initial_weights or dict(zip(self.WEIGHT_NAMES, x0.tolist()))

        improvement = (accuracy_after - accuracy_before) * 100

        return OptimizationResult(
            success=result.success,
            old_weights=old_weights_dict,
            new_weights=new_weights_dict,
            improvement_percentage=improvement,
            accuracy_before=accuracy_before,
            accuracy_after=accuracy_after,
            iterations=result.nit,
            message=result.message if hasattr(result, "message") else "Otimização concluída",
        )

    def _calculate_accuracy(
        self, X: np.ndarray, y: np.ndarray, weights: np.ndarray, threshold: float
    ) -> float:
        """Calcula acurácia para um conjunto de pesos."""
        predictions = (X @ weights > threshold).astype(int)
        return np.mean(predictions == y)

    def cross_validate(
        self,
        historical_data: pd.DataFrame,
        target_column: str = "bought",
        n_splits: int = 5,
        threshold: float = 0.5,
    ) -> Dict:
        """
        Valida a otimização usando cross-validation.

        Args:
            historical_data: DataFrame com features e labels
            target_column: Nome da coluna com labels
            n_splits: Número de folds
            threshold: Threshold para classificação

        Returns:
            Dicionário com métricas de CV
        """
        if len(historical_data) < n_splits:
            return {
                "success": False,
                "message": f"Dados insuficientes ({len(historical_data)} < {n_splits} splits)",
                "accuracies": [],
            }

        fold_size = len(historical_data) // n_splits
        accuracies = []

        for fold in range(n_splits):
            # Split
            test_start = fold * fold_size
            test_end = test_start + fold_size if fold < n_splits - 1 else len(historical_data)

            train_data = pd.concat(
                [historical_data.iloc[:test_start], historical_data.iloc[test_end:]]
            )
            test_data = historical_data.iloc[test_start:test_end]

            if train_data.empty or test_data.empty:
                continue

            # Otimizar com treino
            result = self.optimize(train_data, target_column, threshold=threshold)

            if not result.success:
                continue

            # Avaliar no teste
            X_test = test_data[self.FEATURE_NAMES].values
            y_test = test_data[target_column].values
            weights = np.array([result.new_weights[name] for name in self.WEIGHT_NAMES])

            accuracy = self._calculate_accuracy(X_test, y_test, weights, threshold)
            accuracies.append(accuracy)

        if not accuracies:
            return {
                "success": False,
                "message": "Não foi possível realizar CV",
                "accuracies": [],
            }

        return {
            "success": True,
            "mean_accuracy": np.mean(accuracies),
            "std_accuracy": np.std(accuracies),
            "accuracies": accuracies,
            "n_folds": len(accuracies),
        }
