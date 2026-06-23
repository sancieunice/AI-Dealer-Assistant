from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .entities import data_path

ORDERS_PATH = data_path("orders.json")


def persist_order(order: dict) -> dict:
    """Persist a confirmed dealer order to local JSON storage."""
    record = {
        "order_id": f"ORD-{uuid4().hex[:8].upper()}",
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        **order,
    }
    orders = _load_orders()
    orders.append(record)
    ORDERS_PATH.write_text(json.dumps(orders, indent=2), encoding="utf-8")
    return record


def _load_orders() -> list[dict]:
    if not ORDERS_PATH.exists():
        return []
    return json.loads(ORDERS_PATH.read_text(encoding="utf-8"))
