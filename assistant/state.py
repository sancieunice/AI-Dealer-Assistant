from __future__ import annotations

from typing import Any, Literal, TypedDict


class RetrievedDocument(TypedDict):
    sku: str
    name: str
    category: str
    brand: str
    vehicle_fitment: str
    price_inr: int
    stock: int
    description: str
    score: float


class ToolTrace(TypedDict):
    tool: str
    input: dict[str, Any]
    output: Any


class AssistantState(TypedDict, total=False):
    user_message: str
    normalized_message: str
    history: list[dict[str, str]]
    entities: dict[str, Any]
    metadata_filters: dict[str, str]
    route: Literal["refuse", "clarify", "retrieve", "tool", "answer"]
    clarification_question: str
    retrieved_docs: list[RetrievedDocument]
    tool_traces: list[ToolTrace]
    final_answer: str
    order_summary: dict[str, Any]
