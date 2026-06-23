from __future__ import annotations

from assistant.entities import CatalogueVocabulary, build_metadata_filters, extract_entities
from assistant.retrieval import CatalogueRetriever


def evaluate_retrieval(cases: list[dict], top_k: int = 3) -> dict[str, float]:
    retriever = CatalogueRetriever()
    vocab = CatalogueVocabulary.from_catalogue(retriever.catalogue_path)
    total = 0
    hits = 0
    reciprocal_rank_sum = 0.0
    precision_sum = 0.0

    for case in cases:
        terms = case.get("relevant_terms", [])
        if not terms:
            continue
        total += 1
        entities = extract_entities(case["query"], vocab)
        docs = retriever.search(
            case["query"],
            {"metadata_filters": build_metadata_filters(entities), "entities": entities},
            top_k=top_k,
        )
        relevance = [
            all(term.lower() in " ".join(str(value).lower() for value in doc.values()) for term in terms)
            for doc in docs
        ]
        if any(relevance):
            hits += 1
            reciprocal_rank_sum += 1 / (relevance.index(True) + 1)
        precision_sum += sum(relevance) / max(len(relevance), 1)

    denominator = max(total, 1)
    return {
        "hit_rate": hits / denominator,
        "mrr": reciprocal_rank_sum / denominator,
        "context_precision": precision_sum / denominator,
    }
