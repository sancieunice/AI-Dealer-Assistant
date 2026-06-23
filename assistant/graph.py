from __future__ import annotations

import re

from langgraph.graph import StateGraph, END

from .entities import (
    CatalogueVocabulary,
    build_metadata_filters,
    detect_unsupported_make,
    extract_entities,
    infer_intent,
    is_clearly_off_topic,
    is_focused_order_followup,
    is_new_search,
    is_product_reference_followup,
    is_stock_followup,
    is_topic_exploration,
    normalize,
    normalize_message,
    unsupported_make_message,
)
from .guardrails import (
    clarification_question,
    is_cheapest_query,
    is_in_domain,
    is_pricing_query,
    needs_clarification,
    refusal_message,
)
from .reranker import rerank
from .llm import GroqGenerator
from .memory import ConversationMemory
from .retrieval import CatalogueRetriever
from .state import AssistantState, ToolTrace
from .tools import check_stock, create_order, find_parts_by_vehicle

DISPLAY_LIMIT = 12


def _build_assistant_graph(
    retriever: CatalogueRetriever,
    memory: ConversationMemory,
    generator: GroqGenerator,
    vocab: CatalogueVocabulary,
) -> StateGraph:
    """Build the LangGraph state graph for the assistant."""
    
    graph = StateGraph(AssistantState)
    
    # Define node functions with closure over dependencies
    def guardrail_node(state: AssistantState) -> AssistantState:
        if not is_in_domain(state["user_message"], history=state.get("history"), slots=memory.slots):
            state["route"] = "refuse"
            state["final_answer"] = refusal_message()
        else:
            state["route"] = "answer"
        return state
    
    def entity_node(state: AssistantState) -> AssistantState:
        unsupported = detect_unsupported_make(state["user_message"])
        if unsupported:
            memory.clear_transaction_slots()
            state["entities"] = {}
            state["route"] = "refuse"
            state["final_answer"] = unsupported_make_message(unsupported)
            return state

        extracted = extract_entities(state["user_message"], vocab)

        if is_new_search(state["user_message"]):
            memory.begin_new_search(extracted)
        elif is_topic_exploration(state["user_message"]):
            memory.clear_transaction_slots()
            memory.slots.pop("focus_sku", None)
        elif is_clearly_off_topic(state["user_message"]):
            memory.slots.pop("vehicle_candidates", None)

        entities = memory.merge_slots(extracted)

        keeps_context = (
            is_focused_order_followup(state["user_message"], extracted)
            or is_product_reference_followup(state["user_message"])
            or is_stock_followup(state["user_message"], extracted)
        )
        if not keeps_context:
            if "sku" not in extracted:
                entities.pop("sku", None)
            if "quantity" not in extracted:
                entities.pop("quantity", None)
            if is_topic_exploration(state["user_message"]) or is_new_search(state["user_message"]):
                entities.pop("focus_sku", None)

        active_sku = memory.slots.get("focus_sku") or memory.slots.get("sku")
        if is_product_reference_followup(state["user_message"]) and active_sku:
            entities["sku"] = active_sku
            entities["focus_sku"] = active_sku
            entities["intent"] = infer_intent(normalize(state["user_message"]), entities, state["user_message"])
        elif is_stock_followup(state["user_message"], extracted) and active_sku:
            entities["sku"] = active_sku
            entities["focus_sku"] = active_sku
            entities["intent"] = "check_stock"
        elif is_focused_order_followup(state["user_message"], extracted) and active_sku:
            entities["sku"] = active_sku
            entities["focus_sku"] = active_sku
            entities["intent"] = "create_order"
        elif entities.get("sku") and extracted.get("intent") == "check_stock":
            entities["intent"] = "check_stock"
        elif extracted.get("intent") != "search":
            entities["intent"] = extracted["intent"]

        state["entities"] = entities
        state["metadata_filters"] = build_metadata_filters(entities)
        memory.update_slots(entities)
        for key in ("sku", "quantity", "focus_sku"):
            if key not in entities:
                memory.slots.pop(key, None)
        return state
    
    def clarification_node(state: AssistantState) -> AssistantState:
        if state.get("final_answer"):
            return state
        if needs_clarification(state["entities"], state["user_message"]):
            state["route"] = "clarify"
            state["clarification_question"] = clarification_question(state["entities"])
            state["final_answer"] = state["clarification_question"]
        else:
            state["route"] = "retrieve"
        return state
    
    def retrieval_node(state: AssistantState) -> AssistantState:
        entities = state.get("entities", {})
        filters = state.get("metadata_filters", {}) or {}
        pricing = is_pricing_query(state["user_message"])
        product_keyword = entities.get("product_keyword")

        if filters.get("vehicle_fitment") and filters.get("category"):
            docs = retriever.filter_by_metadata(filters, product_keyword=None)
            if docs and not pricing:
                query = _retrieval_query(state)
                docs = rerank(query, docs, entities, top_k=len(docs))
        else:
            query = _retrieval_query(state)
            docs = retriever.search(query, state, top_k=DISPLAY_LIMIT)

        if pricing:
            docs = sorted(docs, key=lambda doc: doc["price_inr"])

        if product_keyword and not pricing:
            keyword = str(product_keyword).lower()
            if keyword in normalize(state["user_message"]) or keyword.replace(" ", "") in normalize(state["user_message"]).replace(" ", ""):
                keyword_docs = [
                    doc
                    for doc in docs
                    if keyword in doc["name"].lower() or keyword in doc["description"].lower()
                ]
                if keyword_docs:
                    docs = keyword_docs

        state["retrieved_docs"] = docs[:DISPLAY_LIMIT]
        return state
    
    def tool_selection_node(state: AssistantState) -> AssistantState:
        entities = state.get("entities", {})
        traces: list[ToolTrace] = []
        intent = entities.get("intent")

        if intent == "check_stock" and entities.get("sku"):
            sku = str(entities["sku"])
            output = check_stock(sku, retriever)
            traces.append({"tool": "check_stock", "input": {"sku": sku}, "output": output})

        if intent == "find_parts" and entities.get("vehicle"):
            vehicle = str(entities["vehicle"])
            category = str(entities["category"]) if entities.get("category") else None
            output = find_parts_by_vehicle(vehicle, category, retriever, limit=5)
            traces.append(
                {
                    "tool": "find_parts_by_vehicle",
                    "input": {"vehicle": vehicle, "category": category},
                    "output": output,
                }
            )
            if output:
                state["retrieved_docs"] = output

        if intent == "create_order":
            order_payload = _order_payload_from_state(state)
            if order_payload:
                output = create_order(order_payload, retriever)
                traces.append({"tool": "create_order", "input": order_payload, "output": output})
                state["order_summary"] = output
                focus_doc = retriever.by_sku(str(order_payload["items"][0]["sku"]))
                if focus_doc:
                    state["retrieved_docs"] = [focus_doc]

        state["tool_traces"] = traces
        return state
    
    def generation_node(state: AssistantState) -> AssistantState:
        if state.get("order_summary"):
            state["final_answer"] = _format_order(state["order_summary"])
            _remember_order_sku(state["order_summary"], state.get("entities", {}), memory)
            return state

        if state.get("tool_traces"):
            trace = state["tool_traces"][-1]
            if trace["tool"] == "check_stock":
                output = trace["output"]
                if output.get("error"):
                    state["final_answer"] = f"I could not find SKU {output['sku']} in the catalogue."
                else:
                    memory.slots["focus_sku"] = output["sku"]
                    availability = "available" if output["available"] else "out of stock"
                    state["final_answer"] = (
                        f"{output['name']} ({output['sku']}) is {availability}. "
                        f"Stock: {output['stock']} units. Price: INR {output['price_inr']}."
                    )
                return state
            if trace["tool"] == "find_parts_by_vehicle":
                output = trace["output"]
                if not output:
                    state["final_answer"] = "I could not find matching parts for that vehicle in the catalogue."
                else:
                    vehicle = trace["input"].get("vehicle", "the requested vehicle")
                    lines = [f"Here are matching parts for {vehicle}:"]
                    for item in output:
                        lines.append(
                            f"- {item['name']} ({item['sku']}) — INR {item['price_inr']}, stock {item['stock']}"
                        )
                    state["final_answer"] = "\n".join(lines)
                return state

        # Pre-generation guardrail: ensure retrieved docs are relevant
        docs = state.get("retrieved_docs", [])
        entities = state.get("entities", {})
        relevant_docs = _filter_relevant_docs(docs, entities)

        if not relevant_docs:
            state["final_answer"] = "I couldn't find any matching products in the catalogue."
            return state

        if is_cheapest_query(state["user_message"]):
            cheapest_doc = _pick_cheapest_doc(relevant_docs)
            state["final_answer"] = _format_cheapest_answer(relevant_docs, entities)
            state["retrieved_docs"] = [cheapest_doc]
            memory.slots["focus_sku"] = cheapest_doc["sku"]
            return state
        
        # If the LLM is disabled, fall back to a simple list
        if not generator.enabled:
            lines = ["I found these matching catalogue options:"]
            for doc in relevant_docs:
                lines.append(f"- {doc['name']} ({doc['sku']}): INR {doc['price_inr']}, stock {doc['stock']}.")
            state["final_answer"] = "\n".join(lines)
            state["retrieved_docs"] = relevant_docs
            return state

        generated = generator.generate(
            state["user_message"],
            relevant_docs,
            state.get("tool_traces", []),
            history=state.get("history", []),
            slots=memory.slots,
        )
        if generated:
            state["final_answer"] = generated
            state["retrieved_docs"] = relevant_docs
            return state

        return state
    
    def finish_node(state: AssistantState) -> AssistantState:
        memory.add_assistant(state["final_answer"])
        state["history"] = memory.turns
        return state
    
    # Add nodes
    graph.add_node("guardrails", guardrail_node)
    graph.add_node("entity", entity_node)
    graph.add_node("clarification", clarification_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("tools", tool_selection_node)
    graph.add_node("generation", generation_node)
    graph.add_node("finish", finish_node)
    
    # Set entry point
    graph.set_entry_point("guardrails")
    
    # Add conditional edges from guardrails
    graph.add_conditional_edges(
        "guardrails",
        lambda state: "finish" if state["route"] == "refuse" else "entity",
        {"finish": "finish", "entity": "entity"}
    )
    
    # Add conditional edges from clarification
    graph.add_conditional_edges(
        "clarification",
        lambda state: "finish" if state.get("final_answer") or state.get("route") == "clarify" else "retrieval",
        {"finish": "finish", "retrieval": "retrieval"}
    )
    
    # Linear edges for the rest
    graph.add_edge("entity", "clarification")
    graph.add_edge("retrieval", "tools")
    graph.add_edge("tools", "generation")
    graph.add_edge("generation", "finish")
    graph.add_edge("finish", END)
    
    return graph


class AssistantGraph:
    """LangGraph-based assistant with declarative state routing."""

    def __init__(
        self,
        retriever: CatalogueRetriever | None = None,
        memory: ConversationMemory | None = None,
        generator: GroqGenerator | None = None,
    ) -> None:
        self.retriever = retriever or CatalogueRetriever()
        self.memory = memory or ConversationMemory()
        self.generator = generator or GroqGenerator()
        self.vocab = CatalogueVocabulary.from_catalogue(self.retriever.catalogue_path)
        
        # Build the LangGraph
        self.graph = _build_assistant_graph(
            self.retriever,
            self.memory,
            self.generator,
            self.vocab,
        ).compile()

    def invoke(self, message: str) -> AssistantState:
        """Run the assistant graph with the given message."""
        self.memory.add_user(message)
        initial_state: AssistantState = {
            "user_message": message,
            "normalized_message": normalize_message(message),
            "history": self.memory.turns,
            "tool_traces": [],
        }
        
        # Execute the compiled graph
        result = self.graph.invoke(initial_state)
        return result


# Helper functions
def _retrieval_query(state: AssistantState) -> str:
    """Build retrieval query from entities."""
    entities = state.get("entities", {})
    hints = [
        state["user_message"],
        str(entities.get("product_keyword", "")),
        str(entities.get("category", "")),
        str(entities.get("vehicle", "")),
        str(entities.get("brand", "")),
        str(entities.get("sku", "")),
    ]
    return " ".join(hint for hint in hints if hint and hint != "None")


def _order_payload_from_state(state: AssistantState) -> dict | None:
    """Extract order payload from state."""
    entities = state.get("entities", {})
    sku = entities.get("sku") or entities.get("focus_sku")
    if sku is None:
        docs = state.get("retrieved_docs", [])
        if docs:
            sku = docs[0]["sku"]
    if sku is None:
        return None
    return {
        "dealer": str(entities.get("dealer", "Demo Dealer")),
        "items": [{"sku": str(sku), "quantity": int(entities.get("quantity", 1))}],
    }


def _remember_order_sku(order: dict, entities: dict, memory: ConversationMemory) -> None:
    """Keep the discussed SKU in slot memory after order success or failure."""
    sku = None
    items = order.get("items") or []
    if items:
        sku = items[0].get("sku")
    if not sku:
        sku = entities.get("sku") or entities.get("focus_sku")
    if not sku:
        for error in order.get("errors", []):
            match = re.search(r"\b[A-Z]{3}-\d{4}\b", str(error))
            if match:
                sku = match.group(0)
                break
    if sku:
        memory.slots["focus_sku"] = sku
        memory.slots["sku"] = sku


def _format_order(order: dict) -> str:
    """Format order for display."""
    if order["status"] != "ready_for_confirmation":
        errors = "; ".join(order.get("errors", [])) or "order details need attention"
        return f"I could not create a clean order yet: {errors}."
    lines = [f"Order draft for {order['dealer']} is ready for confirmation:"]
    for item in order["items"]:
        lines.append(
            f"- {item['quantity']} x {item['name']} ({item['sku']}) = INR {item['line_total_inr']}"
        )
    lines.append(f"Total: INR {order['total_inr']}.")
    return "\n".join(lines)

def _pick_cheapest_doc(docs: list) -> dict:
    """Pick the lowest-price in-stock item, falling back to the cheapest overall."""
    in_stock = [doc for doc in docs if int(doc["stock"]) > 0]
    pool = in_stock or docs
    return min(pool, key=lambda doc: doc["price_inr"])


def _format_cheapest_answer(docs: list, entities: dict) -> str:
    """Pick the lowest-price in-stock item from the full matching set."""
    cheapest = _pick_cheapest_doc(docs)

    product_label = entities.get("product_keyword") or entities.get("category") or "option"
    vehicle = entities.get("vehicle")
    vehicle_phrase = f" for the {vehicle}" if vehicle else ""

    stock_note = ""
    if int(cheapest["stock"]) <= 0:
        stock_note = " (currently out of stock)"
    elif int(cheapest["stock"]) < 10:
        stock_note = f" (low stock: {cheapest['stock']} units)"

    if len(docs) > 1:
        intro = (
            f"I checked all {len(docs)} matching catalogue options{vehicle_phrase}. "
            f"The cheapest {product_label} is:"
        )
    else:
        intro = f"The cheapest {product_label}{vehicle_phrase} is:"

    return (
        f"{intro}\n"
        f"- {cheapest['name']} ({cheapest['sku']}) by {cheapest['brand']} — "
        f"INR {cheapest['price_inr']}, stock: {cheapest['stock']}{stock_note}."
    )


def _filter_relevant_docs(docs: list, entities: dict) -> list:
    """Filter docs to ensure they are relevant to the user's request."""
    if not entities:
        return docs
    
    relevant_docs = []
    for doc in docs:
        is_relevant = True
        if entities.get("category") and entities["category"] != doc["category"]:
            is_relevant = False
        if entities.get("vehicle") and entities["vehicle"] != doc["vehicle_fitment"]:
            is_relevant = False
        if is_relevant:
            relevant_docs.append(doc)
    return relevant_docs
