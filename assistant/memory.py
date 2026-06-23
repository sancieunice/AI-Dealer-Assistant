from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConversationMemory:
    turns: list[dict[str, str]] = field(default_factory=list)
    slots: dict[str, object] = field(default_factory=dict)

    def add_user(self, message: str) -> None:
        self.turns.append({"role": "user", "content": message})

    def add_assistant(self, message: str) -> None:
        self.turns.append({"role": "assistant", "content": message})

    def update_slots(self, entities: dict[str, object]) -> None:
        if entities.get("vehicle") and entities["vehicle"] != self.slots.get("vehicle"):
            self.slots.pop("dealer", None)
        for key in ("vehicle", "category", "brand", "sku", "quantity", "dealer", "product_keyword", "focus_sku", "vehicle_candidates"):
            if key in entities:
                self.slots[key] = entities[key]

    def clear_transaction_slots(self) -> None:
        for key in ("sku", "focus_sku", "brand", "dealer", "quantity"):
            self.slots.pop(key, None)

    def begin_new_search(self, entities: dict[str, object]) -> None:
        """Drop stale order/stock context when the user starts a fresh parts search."""
        self.clear_transaction_slots()
        self.slots.pop("vehicle_candidates", None)
        if "vehicle" in entities:
            self.slots["vehicle"] = entities["vehicle"]
        elif "vehicle" not in entities:
            self.slots.pop("vehicle", None)
        if "category" in entities:
            self.slots["category"] = entities["category"]
        elif "category" not in entities:
            self.slots.pop("category", None)
        self.slots.pop("product_keyword", None)
        if "product_keyword" in entities:
            self.slots["product_keyword"] = entities["product_keyword"]

    def merge_slots(self, entities: dict[str, object]) -> dict[str, object]:
        merged = dict(self.slots)
        if entities.get("vehicle") and entities["vehicle"] != self.slots.get("vehicle"):
            merged.pop("dealer", None)
        merged.update({key: value for key, value in entities.items() if value})
        if "vehicle" in entities:
            merged.pop("vehicle_candidates", None)
        elif "vehicle_candidates" not in entities:
            merged.pop("vehicle_candidates", None)
        if "intent" in entities:
            merged["intent"] = entities["intent"]
        return merged
