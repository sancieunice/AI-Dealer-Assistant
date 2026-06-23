from __future__ import annotations

from .entities import normalize
from .state import RetrievedDocument


def rerank(
    query: str,
    docs: list[RetrievedDocument],
    entities: dict[str, object],
    top_k: int = 3,
) -> list[RetrievedDocument]:
    terms = set(normalize(query).split())
    reranked: list[RetrievedDocument] = []
    for doc in docs:
        haystack = normalize(
            " ".join(
                [
                    doc["sku"],
                    doc["name"],
                    doc["category"],
                    doc["brand"],
                    doc["vehicle_fitment"],
                    doc["description"],
                ]
            )
        )
        overlap = sum(1 for term in terms if term in haystack)
        metadata_bonus = 0.0
        if entities.get("vehicle") == doc["vehicle_fitment"]:
            metadata_bonus += 2.5
        if entities.get("category") == doc["category"]:
            metadata_bonus += 2.0
        if entities.get("brand") == doc["brand"]:
            metadata_bonus += 1.0
        if entities.get("sku") == doc["sku"]:
            metadata_bonus += 5.0
        if entities.get("product_keyword") and str(entities["product_keyword"]) in haystack:
            metadata_bonus += 2.5
        availability_bonus = 0.25 if int(doc["stock"]) > 0 else 0.0
        doc = dict(doc)
        doc["score"] = float(doc.get("score", 0.0)) + overlap + metadata_bonus + availability_bonus
        reranked.append(doc)  # type: ignore[arg-type]
    return sorted(reranked, key=lambda item: item["score"], reverse=True)[:top_k]
