from __future__ import annotations

from assistant.retrieval import CatalogueRetriever
from assistant.schemas.order_schema import Order


def create_order(payload: dict, retriever: CatalogueRetriever | None = None) -> dict[str, object]:
    retriever = retriever or CatalogueRetriever()
    order = Order.model_validate(payload)
    lines = []
    total = 0
    errors = []

    for item in order.items:
        doc = retriever.by_sku(item.sku)
        if doc is None:
            errors.append(f"{item.sku} was not found")
            continue
        if doc["stock"] < item.quantity:
            errors.append(f"{item.sku} has only {doc['stock']} units in stock")
            continue
        line_total = doc["price_inr"] * item.quantity
        total += line_total
        lines.append(
            {
                "sku": doc["sku"],
                "name": doc["name"],
                "quantity": item.quantity,
                "unit_price_inr": doc["price_inr"],
                "line_total_inr": line_total,
            }
        )

    return {
        "dealer": order.dealer,
        "status": "ready_for_confirmation" if lines and not errors else "needs_attention",
        "items": lines,
        "total_inr": total,
        "errors": errors,
    }
