from __future__ import annotations

from assistant.retrieval import CatalogueRetriever


def check_stock(sku: str, retriever: CatalogueRetriever | None = None) -> dict[str, object]:
    retriever = retriever or CatalogueRetriever()
    doc = retriever.by_sku(sku)
    if doc is None:
        return {"sku": sku.upper(), "available": False, "stock": 0, "error": "SKU not found"}
    return {
        "sku": doc["sku"],
        "name": doc["name"],
        "stock": doc["stock"],
        "available": doc["stock"] > 0,
        "price_inr": doc["price_inr"],
    }
