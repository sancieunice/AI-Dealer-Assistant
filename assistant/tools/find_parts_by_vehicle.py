from __future__ import annotations

from assistant.retrieval import CatalogueRetriever


def find_parts_by_vehicle(
    vehicle: str,
    category: str | None = None,
    retriever: CatalogueRetriever | None = None,
    limit: int = 10,
) -> list[dict[str, object]]:
    retriever = retriever or CatalogueRetriever()
    filters: dict[str, str] = {"vehicle_fitment": vehicle}
    if category:
        filters["category"] = category
    entities: dict[str, object] = {"vehicle": vehicle}
    if category:
        entities["category"] = category
    state = {"metadata_filters": filters, "entities": entities}
    query = vehicle if not category else f"{category} {vehicle}"
    docs = retriever.search(query, state, top_k=limit)
    return [
        {
            "sku": doc["sku"],
            "name": doc["name"],
            "category": doc["category"],
            "brand": doc["brand"],
            "price_inr": doc["price_inr"],
            "stock": doc["stock"],
        }
        for doc in docs
    ]
