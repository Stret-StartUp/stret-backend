"""
Admin endpoints para gerenciamento de modelo de scoring.

Responsabilidades:
- Otimizar pesos baseado em histórico de compras
- Visualizar pesos atuais
- Reset para valores padrão
"""

from typing import Dict, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
import pandas as pd
from pandas import io

from app.services.analytics.intelligent_weighting import IntelligentWeightingService
from app.services.analytics.weight_optimizer import WeightOptimizer, OptimizationResult

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Serviços
weighting_service = IntelligentWeightingService()
optimizer = WeightOptimizer()


@router.get("/weights", response_model=Dict[str, float])
async def get_current_weights():
    """
    Retorna os pesos atuais de scoring.
    
    Exemplo:
    ```json
    {
        "event_similarity_weight": 0.25,
        "affinity_weight": 0.25,
        ...
    }
    ```
    """
    return weighting_service.get_weights()


@router.post("/weights/reset")
async def reset_weights_to_defaults():
    """
    Reseta pesos para valores padrão do settings.
    
    Response:
    ```json
    {
        "status": "reset",
        "weights": {...}
    }
    ```
    """
    weighting_service.reset_to_defaults()
    return {
        "status": "reset",
        "weights": weighting_service.get_weights(),
    }


@router.post("/weights/update")
async def update_weights(new_weights: Dict[str, float]):
    """
    Atualiza manualmente os pesos de scoring.
    
    Deve conter chaves: event_similarity_weight, affinity_weight, etc.
    
    Body:
    ```json
    {
        "event_similarity_weight": 0.3,
        "affinity_weight": 0.3,
        "ticket_weight": 0.2,
        "age_weight": 0.1,
        "purchase_timing_weight": 0.05,
        "vibe_weight": 0.03,
        "frequency_weight": 0.02
    }
    ```
    """
    success = weighting_service.update_weights(new_weights)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Pesos inválidos. Verifique que todos são não-negativos."
        )
    
    return {
        "status": "updated",
        "weights": weighting_service.get_weights(),
    }


@router.post("/optimize-weights")
async def optimize_weights_from_history(
    historical_data_path: Optional[str] = Query(None),
    threshold: float = Query(0.5, ge=0.0, le=1.0),
    max_iterations: int = Query(1000, ge=100),
):
    """
    Otimiza pesos usando histórico de compras.
    
    ⚠️ ENDPOINT PLACEHOLDER: Requer integração com dados reais
    
    Query params:
    - historical_data_path: Caminho para arquivo CSV com histórico
    - threshold: Threshold para classificação (default 0.5)
    - max_iterations: Máximo de iterações (default 1000)
    
    CSV esperado:
    event_similarity_score,affinity_score,ticket_score,age_score,purchase_timing_score,vibe_score,frequency_score,bought
    0.8,0.7,0.6,0.5,0.4,0.3,0.2,1
    ...
    """
    raise HTTPException(
        status_code=501,
        detail="Endpoint de otimização requer implementação de upload de histórico. "
               "Use o POST /api/v1/upload para adicionar histórico primeiro."
    )


@router.post("/validate-weights")
async def validate_weights(weights: Dict[str, float]):
    """
    Valida um conjunto de pesos sem aplicá-los.
    
    Response:
    ```json
    {
        "valid": true,
        "message": "Pesos válidos"
    }
    ```
    """
    from app.services.analytics.intelligent_weighting import IntelligentWeights
    
    try:
        w = IntelligentWeights.from_dict(weights)
        is_valid = w.validate()
        
        return {
            "valid": is_valid,
            "message": "Pesos válidos" if is_valid else "Contém peso negativo"
        }
    except Exception as e:
        return {
            "valid": False,
            "message": f"Erro: {str(e)}"
        }


@router.post("/optimize-weights")
async def optimize_weights_from_history(file: UploadFile = File(...), threshold: float = 0.5):
    contents = await file.read()
    df = pd.read_csv(io.BytesIO(contents))
    
    result = optimizer.optimize(df, initial_weights=weighting_service.get_weights(), threshold=threshold)
    
    if result.success:
        weighting_service.update_weights(result.new_weights)
    
    return result