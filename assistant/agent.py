from __future__ import annotations

from .graph import AssistantGraph
from .memory import ConversationMemory
from .retrieval import CatalogueRetriever
from .state import AssistantState


class DealerAssistant:
    def __init__(self) -> None:
        self.memory = ConversationMemory()
        self.retriever = CatalogueRetriever()
        self.graph = AssistantGraph(self.retriever, self.memory)

    def chat(self, message: str) -> AssistantState:
        return self.graph.invoke(message)

    def reset(self) -> None:
        self.memory.turns.clear()
        self.memory.slots.clear()
