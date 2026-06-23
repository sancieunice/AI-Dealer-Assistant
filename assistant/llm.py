from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .prompts import SYSTEM_PROMPT
from .state import RetrievedDocument, ToolTrace


DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"


class GroqGenerator:
    def __init__(self, model: str | None = None) -> None:
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        self._client: Any | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def generate(
        self,
        user_message: str,
        docs: list[RetrievedDocument],
        tool_traces: list[ToolTrace],
        history: list[dict[str, str]] | None = None,
        slots: dict[str, object] | None = None,
    ) -> str | None:
        if not self.enabled:
            return None
        try:
            from groq import Groq
        except ImportError:
            return None

        if self._client is None:
            self._client = Groq(api_key=self.api_key)

        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
            ]
            
            # Add conversation history (excluding the most recent user message)
            if history:
                for turn in history[:-1]:
                    messages.append(turn)
            
            # Add current user message with context
            messages.append({
                "role": "user",
                "content": self._build_prompt(user_message, docs, tool_traces, slots),
            })
            
            completion = self._client.chat.completions.create(
                model=self.model,
                temperature=0.1,
                max_tokens=450,
                messages=messages,
            )
            return completion.choices[0].message.content
        except Exception as e:
            logging.error("Failed to generate response from Groq: %s", e)
            return None

    @staticmethod
    def _build_prompt(
        user_message: str,
        docs: list[RetrievedDocument],
        tool_traces: list[ToolTrace],
        slots: dict[str, object] | None = None,
    ) -> str:
        context_lines = []
        for doc in docs:
            context_lines.append(
                "\n".join(
                    [
                        f"SKU: {doc['sku']}",
                        f"Name: {doc['name']}",
                        f"Category: {doc['category']}",
                        f"Brand: {doc['brand']}",
                        f"Vehicle Fitment: {doc['vehicle_fitment']}",
                        f"Price INR: {doc['price_inr']}",
                        f"Stock: {doc['stock']}",
                        f"Description: {doc['description']}",
                    ]
                )
            )

        tool_info = ""
        if tool_traces:
            tool_lines = []
            for trace in tool_traces:
                tool_lines.append(f"Tool: {trace['tool']}, Result: {trace['output']}")
            tool_info = f"Tool traces:\n{chr(10).join(tool_lines)}\n\n"

        # Format slot memory
        slot_info = ""
        if slots:
            slot_lines = []
            slot_keys = ["category", "vehicle", "brand", "quantity", "dealer"]
            for key in slot_keys:
                value = slots.get(key)
                slot_lines.append(f"{key} = {value if value else 'None'}")
            slot_info = f"Current extracted slots:\n{chr(10).join(slot_lines)}\n\n"

        return (
            f"Latest dealer question:\n{user_message}\n\n"
            f"{slot_info}"
            f"Retrieved catalogue context:\n{chr(10).join(context_lines) or 'None'}\n\n"
            f"{tool_info}"
            "Write a concise dealer-facing answer. Use only this context. "
            "Include product name, SKU, price and stock when recommending products."
        )
