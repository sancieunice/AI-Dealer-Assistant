from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class OrderItem(BaseModel):
    sku: str = Field(..., min_length=3)
    quantity: int = Field(..., gt=0, le=10000)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.upper().strip()


class Order(BaseModel):
    dealer: str = Field(..., min_length=2)
    items: list[OrderItem] = Field(..., min_length=1)
