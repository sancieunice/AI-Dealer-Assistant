from __future__ import annotations

from assistant.agent import DealerAssistant
from assistant.entities import CatalogueVocabulary, build_metadata_filters, extract_entities
from assistant.retrieval import CatalogueRetriever


def evaluate_generation(
    cases: list[dict],
    return_details: bool = False,
) -> dict[str, float] | tuple[dict[str, float], list[dict]]:
    case_results: list[dict] = []
    route_hits = 0
    tool_hits = 0
    total_tools = 0
    grounded_hits = 0
    clarification_hits = 0
    clarification_total = 0

    for case in cases:
        if "turns" in case:
            assistant = DealerAssistant()
            for index, turn in enumerate(case["turns"], start=1):
                state = assistant.chat(turn["query"])
                flat_case = {
                    "id": f"{case['id']}_turn{index}",
                    "parent_id": case["id"],
                    "category": case.get("category", "multi_turn"),
                    **turn,
                }
                result = evaluate_case(flat_case, state)
                case_results.append(result)
        else:
            assistant = DealerAssistant()
            state = assistant.chat(case["query"])
            case_results.append(evaluate_case(case, state))

    for result in case_results:
        checks = result["checks"]
        if checks.get("route_ok"):
            route_hits += 1
        if checks.get("expected_tool"):
            total_tools += 1
            if checks.get("tool_ok"):
                tool_hits += 1
        if checks.get("grounding_ok"):
            grounded_hits += 1
        if result.get("expected_route") == "clarify":
            clarification_total += 1
            if checks.get("route_ok") and checks.get("answer_ok"):
                clarification_hits += 1

    total = max(len(case_results), 1)
    metrics = {
        "route_accuracy": route_hits / total,
        "tool_accuracy": tool_hits / max(total_tools, 1),
        "grounding_accuracy": grounded_hits / total,
        "clarification_accuracy": clarification_hits / max(clarification_total, 1),
        "overall_success_rate": sum(1 for result in case_results if result["passed"]) / total,
    }
    if return_details:
        return metrics, case_results
    return metrics


def evaluate_case(case: dict, state: dict) -> dict:
    answer = state.get("final_answer", "")
    docs = state.get("retrieved_docs", [])
    tool_outputs = " ".join(str(trace["output"]) for trace in state.get("tool_traces", []))
    expected_tool = case.get("expected_tool")
    actual_tools = [trace["tool"] for trace in state.get("tool_traces", [])]

    route_ok = state.get("route") == case.get("expected_route")
    tool_ok = not expected_tool or expected_tool in actual_tools
    answer_ok = all(
        fragment.lower() in answer.lower() for fragment in case.get("answer_must_contain", [])
    )
    grounding_ok = _is_grounded(answer, docs, tool_outputs, case.get("expected_route"))
    retrieval_ok = _retrieval_ok(case, docs)

    checks = {
        "route_ok": route_ok,
        "tool_ok": tool_ok,
        "answer_ok": answer_ok,
        "grounding_ok": grounding_ok,
        "retrieval_ok": retrieval_ok,
        "expected_tool": expected_tool,
        "relevant_terms": case.get("relevant_terms", []),
    }
    passed = route_ok and tool_ok and answer_ok and grounding_ok and (
        not case.get("relevant_terms") or retrieval_ok
    )
    return {
        "id": case["id"],
        "category": case.get("category", "unknown"),
        "query": case.get("query"),
        "expected_route": case.get("expected_route"),
        "actual_route": state.get("route"),
        "tools": actual_tools,
        "passed": passed,
        "checks": checks,
        "answer_preview": answer[:240],
    }


def _is_grounded(
    answer: str,
    docs: list[dict],
    tool_outputs: str,
    expected_route: str | None,
) -> bool:
    if expected_route in {"refuse", "clarify"}:
        return True
    if not docs and not tool_outputs:
        return False
    if tool_outputs and any(str(doc["sku"]) in tool_outputs for doc in docs):
        return True
    return any(str(doc["sku"]) in answer for doc in docs) or bool(tool_outputs)


def _retrieval_ok(case: dict, docs: list[dict]) -> bool:
    terms = case.get("relevant_terms", [])
    if not terms or not docs:
        return not terms
    return any(
        all(term.lower() in " ".join(str(value).lower() for value in doc.values()) for term in terms)
        for doc in docs[:3]
    )
