from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ProductOption(BaseModel):
    sku: str
    name: str
    price_inr: int
    stock: int


class AssistantResponse(BaseModel):
    response_type: Literal["answer", "clarification", "refusal", "order"]
    message: str
    products: list[ProductOption] = []
    tool_traces: list[dict] = []
