from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def data_path(filename: str) -> Path:
    data_candidate = ROOT / "data" / filename
    return data_candidate if data_candidate.exists() else ROOT / filename


@dataclass(frozen=True)
class CatalogueVocabulary:
    vehicles: tuple[str, ...]
    categories: tuple[str, ...]
    brands: tuple[str, ...]
    skus: tuple[str, ...]

    @classmethod
    def from_catalogue(cls, catalogue_path: Path | None = None) -> "CatalogueVocabulary":
        df = pd.read_csv(catalogue_path or data_path("catalogue.csv"))
        return cls(
            vehicles=tuple(sorted(df["vehicle_fitment"].dropna().unique(), key=len, reverse=True)),
            categories=tuple(sorted(df["category"].dropna().unique(), key=len, reverse=True)),
            brands=tuple(sorted(df["brand"].dropna().unique(), key=len, reverse=True)),
            skus=tuple(sorted(df["sku"].dropna().unique())),
        )


CATEGORY_ALIASES = {
    "brake": "Brakes",
    "brakes": "Brakes",
    "pad": "Brakes",
    "pads": "Brakes",
    "tyre": "Tyres & Tubes",
    "tire": "Tyres & Tubes",
    "tube": "Tyres & Tubes",
    "filter": "Filters",
    "oil": "Lubricants",
    "chain": "Drivetrain",
    "clutch": "Drivetrain",
    "battery": "Electricals",
    "mirror": "Body & Styling",
    "seat cover": "Car Care & Accessories",
}

PRODUCT_HINTS = {
    "brake pad": ("Brakes", "brake pad"),
    "brake pads": ("Brakes", "brake pad"),
    "brake disc": ("Brakes", "brake disc"),
    "disc rotor": ("Brakes", "disc rotor"),
    "brake lever": ("Brakes", "brake lever"),
    "tyre": ("Tyres & Tubes", "tyre"),
    "tire": ("Tyres & Tubes", "tyre"),
    "tube": ("Tyres & Tubes", "tube"),
    "oil filter": ("Filters", "oil filter"),
    "air filter": ("Filters", "air filter"),
    "clutch plate": ("Drivetrain", "clutch plate"),
    "chain kit": ("Drivetrain", "chain kit"),
    "chain lube": ("Drivetrain", "chain lube"),
    "battery": ("Electricals", "battery"),
    "mirror": ("Body & Styling", "mirror"),
}

ORDER_VERBS = {"order", "buy", "purchase", "place", "create"}
STOCK_VERBS = {"available", "availability", "inventory"}
STOCK_PHRASES = (
    "check stock",
    "stock level",
    "stock for",
    "stock of",
    "in stock",
    "out of stock",
    "how many",
    "units left",
    "units available",
)
CATALOGUE_STOCK_PHRASES = ("do you stock", "you stock", "we stock", "you carry", "you sell")
PRODUCT_REFERENCE_PHRASES = (
    " it ",
    " it?",
    "that one",
    "this one",
    "that product",
    "this product",
    "the cheapest",
    "does it have",
    "does that have",
)
SPELLING_FIXES = {
    "breaks": "brakes",
    "breakes": "brakes",
    "break pad": "brake pad",
    "break pads": "brake pads",
    "ferari": "ferrari",
    "fereari": "ferrari",
    "ferrari": "ferrari",
    "pulsur": "pulsar",
    "pulser": "pulsar",
    "duke": "duke",
    "tyer": "tyre",
    "tyers": "tyres",
    "tires": "tyres",
    "enfield": "enfield",
}
OFF_TOPIC_TERMS = {
    "weather",
    "joke",
    "jokes",
    "funny",
    "politics",
    "recipe",
    "football",
    "cricket score",
    "tell me a story",
    "who are you",
    "how are you",
}
SEARCH_STARTERS = ("need", "show", "find", "looking for", "want", "get", "do you have", "any")
UNSUPPORTED_MAKES = {
    "ferrari",
    "lamborghini",
    "tesla",
    "bmw",
    "mercedes",
    "audi",
    "porsche",
    "maserati",
    "bugatti",
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def normalize_message(text: str) -> str:
    """Normalize text and fix common catalogue spelling mistakes."""
    cleaned = normalize(text)
    for wrong, right in sorted(SPELLING_FIXES.items(), key=lambda item: len(item[0]), reverse=True):
        cleaned = cleaned.replace(wrong, right)
    return cleaned


def is_clearly_off_topic(message: str) -> bool:
    text = normalize_message(message)
    return any(term in text for term in OFF_TOPIC_TERMS)


def detect_unsupported_make(message: str) -> str | None:
    text = normalize_message(message)
    for make in UNSUPPORTED_MAKES:
        if re.search(rf"\b{re.escape(make)}\b", text):
            return make.title()
    return None


def unsupported_make_message(make: str) -> str:
    return (
        f"We don't carry {make} parts in our catalogue. "
        "I can help only with motorcycle and scooter parts from our listed inventory."
    )


def _short_model_name(vehicle: str) -> str:
    parts = vehicle.split()
    if len(parts) >= 2:
        return " ".join(parts[-2:])
    return vehicle


def is_pricing_followup(message: str) -> bool:
    text = normalize_message(message)
    pricing_terms = {"cheapest", "cheaper", "lowest", "affordable", "expensive", "price", "cost", "compare"}
    return any(term in text for term in pricing_terms)


def is_new_search(message: str) -> bool:
    text = normalize_message(message)
    if is_product_reference_followup(message):
        return False
    if is_pricing_followup(message):
        return False
    if any(verb in text for verb in ORDER_VERBS):
        return False
    return any(text.startswith(starter) or f" {starter} " in f" {text} " for starter in SEARCH_STARTERS)


def _contains_phrase(text: str, phrase: str) -> bool:
    return phrase.lower() in text


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _collect_vehicle_matches(token: str, compact_vehicles: dict[str, str]) -> list[str]:
    compact_token = _compact(token)
    if not compact_token:
        return []

    token_matches = [
        vehicle
        for compact_name, vehicle in compact_vehicles.items()
        if compact_token in compact_name.split() or compact_token in compact_name
    ]
    if token_matches:
        return sorted(set(token_matches))

    prefix_matches = [
        vehicle
        for compact_name, vehicle in compact_vehicles.items()
        if compact_name.startswith(compact_token) or compact_token.startswith(compact_name)
    ]
    if prefix_matches:
        return sorted(set(prefix_matches))

    fuzzy = get_close_matches(compact_token, compact_vehicles.keys(), n=3, cutoff=0.75)
    if fuzzy:
        return sorted({compact_vehicles[name] for name in fuzzy})
    return []


def _resolve_vehicle(text: str, vocab: CatalogueVocabulary) -> tuple[str | None, list[str]]:
    normalized = normalize_message(text)

    for vehicle in vocab.vehicles:
        if vehicle != "Universal" and _contains_phrase(normalized, vehicle.lower()):
            return vehicle, []

    compact_vehicles = {_compact(vehicle): vehicle for vehicle in vocab.vehicles if vehicle != "Universal"}
    candidate_phrases: list[str] = [normalized]
    for_match = re.search(r"\bfor\s+([a-z0-9 &.-]{2,40})", normalized)
    if for_match:
        candidate_phrases.insert(0, for_match.group(1).strip())

    for phrase in candidate_phrases:
        matches = _collect_vehicle_matches(phrase, compact_vehicles)
        if len(matches) == 1:
            return matches[0], []
        if len(matches) > 1:
            return None, matches

    text_words = {word for word in _compact(normalized).split() if len(word) > 2}
    token_hits: dict[str, list[str]] = {}
    for vehicle in vocab.vehicles:
        if vehicle == "Universal":
            continue
        vehicle_words = set(_compact(vehicle).split())
        overlap = vehicle_words & text_words
        for word in overlap:
            token_hits.setdefault(word, []).append(vehicle)

    for word in sorted(text_words, key=len, reverse=True):
        matches = sorted(set(token_hits.get(word, [])))
        if len(matches) == 1:
            return matches[0], []
        if len(matches) > 1:
            return None, matches

    fuzzy = get_close_matches(_compact(normalized), compact_vehicles.keys(), n=1, cutoff=0.6)
    if fuzzy:
        return compact_vehicles[fuzzy[0]], []
    return None, []


def _match_vehicle(text: str, vocab: CatalogueVocabulary) -> str | None:
    vehicle, _ = _resolve_vehicle(text, vocab)
    return vehicle


def extract_entities(message: str, vocab: CatalogueVocabulary) -> dict[str, object]:
    text = normalize_message(message)
    entities: dict[str, object] = {}

    sku_match = re.search(r"\b[A-Z]{3}-\d{4}\b", message.upper())
    if sku_match:
        entities["sku"] = sku_match.group(0)

    quantity_match = re.search(r"\b(?:qty|quantity|x)?\s*(\d{1,4})\s*(?:pcs|pieces|units|sets)?\b", text)
    if quantity_match and any(verb in text for verb in ORDER_VERBS):
        entities["quantity"] = int(quantity_match.group(1))

    vehicle, vehicle_candidates = _resolve_vehicle(text, vocab)
    if vehicle:
        entities["vehicle"] = vehicle
    elif len(vehicle_candidates) > 1:
        entities["vehicle_candidates"] = vehicle_candidates

    if "vehicle" not in entities:
        dealer = _extract_dealer_name(message, vocab)
        if dealer:
            entities["dealer"] = dealer

    for category in vocab.categories:
        if _contains_phrase(text, category):
            entities["category"] = category
            break

    for hint, (category, product_keyword) in PRODUCT_HINTS.items():
        if hint in text:
            entities.setdefault("category", category)
            entities["product_keyword"] = product_keyword
            break

    if "category" not in entities:
        for alias, category in CATEGORY_ALIASES.items():
            if alias in text:
                entities["category"] = category
                break

    for brand in vocab.brands:
        if _contains_phrase(text, brand):
            entities["brand"] = brand
            break

    entities["intent"] = infer_intent(text, entities, message)
    return entities


def _looks_like_vehicle_name(candidate: str, vocab: CatalogueVocabulary) -> bool:
    token = _compact(candidate)
    if not token:
        return False
    for vehicle in vocab.vehicles:
        if token in _compact(vehicle).split():
            return True
    return bool(get_close_matches(token, [_compact(v) for v in vocab.vehicles if v != "Universal"], n=1, cutoff=0.8))


def _extract_dealer_name(message: str, vocab: CatalogueVocabulary | None = None) -> str | None:
    """Extract dealer name from the last 'for <name>' phrase in an order request."""
    candidates = re.findall(r"\bfor\s+([A-Za-z][A-Za-z0-9 &.-]{1,39})", message)
    for candidate in reversed(candidates):
        cleaned = candidate.strip().rstrip(".")
        if vocab and _looks_like_vehicle_name(cleaned, vocab):
            continue
        if re.search(r"\b\d+\b", cleaned):
            continue
        if re.search(r"\b(units?|pcs|pieces|sets?|sku)\b", cleaned, flags=re.I):
            continue
        if re.search(r"\b[A-Z]{3}-\d{4}\b", cleaned):
            continue
        return cleaned
    return None


def is_topic_exploration(message: str) -> bool:
    text = normalize_message(message)
    return any(text.startswith(prefix) for prefix in ("what about", "how about", "wat about", "tell me about"))


def is_focused_order_followup(message: str, entities: dict[str, object] | None = None) -> bool:
    """True when the user wants to order the already-discussed SKU (e.g. 'order 6 units')."""
    text = normalize_message(message)
    if not any(verb in text for verb in ORDER_VERBS):
        return False
    if detect_unsupported_make(message):
        return False
    if entities and entities.get("sku"):
        return True
    if re.search(r"\b[A-Z]{3}-\d{4}\b", message.upper()):
        return True
    if re.search(r"\b(order|buy|purchase|place)\b\s+(it|that|this)\b", text):
        return True
    if re.search(r"\b(order|buy|purchase|place)\b", text) and re.search(
        r"\b\d+\s*(units|unit|pcs|pieces)?\b", text
    ):
        return True
    if re.search(r"\b(place|create)\s+an?\s+order\b", text) and len(text.split()) <= 5:
        return True
    return False


def is_product_reference_followup(message: str) -> bool:
    text = f" {normalize(message)} "
    return any(phrase in text for phrase in PRODUCT_REFERENCE_PHRASES)


def is_stock_followup(message: str, extracted: dict[str, object] | None = None) -> bool:
    """Bare stock question that should reuse the SKU from the previous turn."""
    text = normalize_message(message)
    entities = extracted or {}
    if entities.get("sku"):
        return False
    if entities.get("vehicle") or entities.get("category"):
        return False
    return _is_stock_lookup_query(text, entities)


def _is_stock_lookup_query(text: str, entities: dict[str, object]) -> bool:
    if "sku" in entities and any(phrase in text for phrase in STOCK_PHRASES):
        return True
    if re.search(r"\b(how much|what).{0,20}\bstock\b", text):
        return True
    if re.search(r"\bstock\b.{0,20}\b(it|that|this)\b", text):
        return True
    if any(phrase in text for phrase in CATALOGUE_STOCK_PHRASES):
        return False
    if any(verb in text for verb in STOCK_VERBS):
        return True
    return any(phrase in text for phrase in STOCK_PHRASES)


def infer_intent(text: str, entities: dict[str, object], message: str = "") -> str:
    if any(verb in text for verb in ORDER_VERBS):
        if is_focused_order_followup(message or text, entities):
            return "create_order"
        return "search"
    if _is_stock_lookup_query(text, entities):
        return "check_stock"
    if "vehicle" in entities and any(
        phrase in text for phrase in ("parts for", "fit", "compatible", "have", "show", "find")
    ):
        return "find_parts"
    return "search"


def build_metadata_filters(entities: dict[str, object]) -> dict[str, str]:
    filters: dict[str, str] = {}
    if vehicle := entities.get("vehicle"):
        filters["vehicle_fitment"] = str(vehicle)
    if category := entities.get("category"):
        filters["category"] = str(category)
    if brand := entities.get("brand"):
        filters["brand"] = str(brand)
    if sku := entities.get("sku"):
        filters["sku"] = str(sku)
    return filters
