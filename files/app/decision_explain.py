from __future__ import annotations

from app.purchasing_engine import PurchasingRecommendation


ENGINE_VERSION = "1.0.0"


def explain(recommendation: PurchasingRecommendation) -> str:
    if recommendation.average_daily_consumption <= 0:
        return (
            f"{recommendation.internal_code}: não há consumo suficiente "
            "no período para recomendar compra automática."
        )

    decision = (
        f"Comprar {recommendation.suggested_quantity:.0f} unidade(s)"
        if recommendation.suggested_quantity > 0
        else "Não comprar agora"
    )
    cover = (
        f"{recommendation.days_of_cover:.1f} dias"
        if recommendation.days_of_cover is not None
        else "indeterminada"
    )
    supplier = (
        recommendation.best_quote_supplier_name
        or recommendation.preferred_supplier_name
        or "a definir"
    )

    return (
        f"{decision}. Consumo médio: "
        f"{recommendation.average_daily_consumption:.2f} unidade(s)/dia; "
        f"estoque disponível: {recommendation.available_stock:.2f}; "
        f"cobertura: {cover}; lead time: "
        f"{recommendation.lead_time_days} dia(s); estoque de segurança: "
        f"{recommendation.safety_stock:.2f}; ponto de reposição: "
        f"{recommendation.reorder_point:.2f}; fornecedor de referência: "
        f"{supplier}. Classe ABC: {recommendation.abc_class}."
    )
