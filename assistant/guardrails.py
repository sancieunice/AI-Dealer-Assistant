from __future__ import annotations

from .entities import is_clearly_off_topic, is_product_reference_followup, normalize


DOMAIN_TERMS = {
    "part",
    "parts",
    "sku",
    "stock",
    "available",
    "order",
    "dealer",
    "vehicle",
    "bike",
    "car",
    "brake",
    "brakes",
    "tyre",
    "tire",
    "filter",
    "clutch",
    "chain",
    "battery",
    "mirror",
    "engine",
    "oil",
    "pulsar",
    "honda",
    "yamaha",
    "bajaj",
    "tvs",
    "hero",
    "ktm",
    "maruti",
    "hyundai",
    "kia",
    "mahindra",
    "enfield",
    "suzuki",
    # Pricing and comparison terms
    "price",
    "cost",
    "cheapest",
    "cheap",
    "expensive",
    "cheaper",
    "dearer",
    "affordable",
    "compare",
    "comparison",
    "inr",
    "rupees",
}


def is_in_domain(message: str, history: list[dict[str, str]] | None = None, slots: dict[str, object] | None = None) -> bool:
    """Check if message is in domain. Also considers conversation history and slots."""
    text = normalize(message)

    if is_clearly_off_topic(message):
        return False

    # Direct domain term match
    if any(term in text for term in DOMAIN_TERMS):
        return True

    # Contextual follow-ups can rely on prior turns or slots
    if is_product_reference_followup(message) or is_pricing_query(message):
        if history and len(history) > 0:
            for turn in history:
                content = normalize(turn.get("content", ""))
                if any(term in content for term in DOMAIN_TERMS):
                    return True
        if slots and any(slots.get(slot) for slot in ("vehicle", "category", "brand", "sku")):
            return True

    # Prior domain conversation keeps short follow-ups in scope
    if history and len(history) > 0:
        for turn in history[-4:]:
            content = normalize(turn.get("content", ""))
            if any(term in content for term in DOMAIN_TERMS):
                if len(text.split()) <= 8:
                    return True

    return False


def refusal_message() -> str:
    return "I can help only with automotive parts, stock information and dealer orders."


PRICING_TERMS = {"cheapest", "price", "cost", "compare", "affordable", "cheaper", "expensive", "lowest"}
CHEAPEST_TERMS = {"cheapest", "cheaper", "affordable", "lowest"}


def is_pricing_query(message: str) -> bool:
    text = normalize(message)
    return any(term in text for term in PRICING_TERMS)


def is_cheapest_query(message: str) -> bool:
    text = normalize(message)
    return any(term in text for term in CHEAPEST_TERMS)


def needs_clarification(entities: dict[str, object], message: str) -> bool:
    intent = entities.get("intent")
    vehicle_candidates = entities.get("vehicle_candidates", [])

    if vehicle_candidates and len(vehicle_candidates) > 1 and "vehicle" not in entities:
        return True

    if intent == "check_stock":
        return "sku" not in entities and not ("vehicle" in entities and "category" in entities)
    if intent == "create_order":
        return "sku" not in entities and not ("vehicle" in entities and "category" in entities)
    if intent == "search":
        if is_pricing_query(message):
            has_vehicle = "vehicle" in entities
            has_category = "category" in entities
            has_product = "product_keyword" in entities
            return not (has_vehicle or has_category or has_product)

        has_vehicle = "vehicle" in entities
        has_category = "category" in entities
        has_sku = "sku" in entities
        if has_sku:
            return False
        return (has_vehicle and not has_category) or (has_category and not has_vehicle)
    return False


def clarification_question(entities: dict[str, object]) -> str:
    vehicle_candidates = entities.get("vehicle_candidates", [])
    if vehicle_candidates and len(vehicle_candidates) > 1:
        labels = [_short_model_label(str(vehicle)) for vehicle in vehicle_candidates]
        if len(labels) == 2:
            return f"Did you mean {labels[0]} or {labels[1]}?"
        options = ", ".join(labels[:-1]) + f", or {labels[-1]}"
        return f"Which model did you mean: {options}?"

    category = entities.get("category")
    if category:
        return f"Which vehicle model do you need {str(category).lower()} for?"
    return "Which vehicle model or SKU should I look up?"


def _short_model_label(vehicle: str) -> str:
    parts = vehicle.split()
    if len(parts) >= 2:
        return " ".join(parts[-2:])
    return vehicle
