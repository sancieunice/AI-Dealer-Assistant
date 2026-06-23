from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from assistant.agent import DealerAssistant
from eval.generation_eval import evaluate_case, evaluate_generation
from eval.retrieval_eval import evaluate_retrieval


def _flatten_cases(cases: list[dict]) -> list[dict]:
  flat: list[dict] = []
  for case in cases:
    if "turns" in case:
      for index, turn in enumerate(case["turns"], start=1):
        flat.append(
          {
            "id": f"{case['id']}_turn{index}",
            "parent_id": case["id"],
            "category": case.get("category", "multi_turn"),
            **turn,
          }
        )
    else:
      flat.append(case)
  return flat


def _run_multi_turn(case: dict) -> list[dict]:
  assistant = DealerAssistant()
  results = []
  for index, turn in enumerate(case["turns"], start=1):
    state = assistant.chat(turn["query"])
    result = evaluate_case(
      {
        "id": f"{case['id']}_turn{index}",
        "parent_id": case["id"],
        "category": case.get("category", "multi_turn"),
        **turn,
      },
      state,
    )
    results.append(result)
  return results


def main() -> None:
  cases = json.loads(Path("eval/test_cases.json").read_text(encoding="utf-8"))
  flat_cases = _flatten_cases(cases)

  retrieval_metrics = evaluate_retrieval(flat_cases)
  generation_metrics, case_results = evaluate_generation(cases, return_details=True)

  failures = [result for result in case_results if not result["passed"]]
  failure_modes = _summarize_failures(failures)

  payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "case_count": len(case_results),
    "retrieval": retrieval_metrics,
    "generation": generation_metrics,
    "cases": case_results,
    "failure_analysis": failure_modes,
  }

  results_json = Path("eval/results.json")
  results_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

  results_md = _render_markdown(payload)
  Path("eval/results.md").write_text(results_md, encoding="utf-8")

  print("Retrieval")
  for key, value in retrieval_metrics.items():
    print(f"  {key}: {value:.3f}")
  print("Generation")
  for key, value in generation_metrics.items():
    print(f"  {key}: {value:.3f}")
  print(f"Cases passed: {sum(1 for result in case_results if result['passed'])}/{len(case_results)}")
  print(f"Wrote {results_json} and eval/results.md")


def _summarize_failures(failures: list[dict]) -> dict[str, list[str]]:
  buckets: dict[str, list[str]] = {
    "routing": [],
    "tool_selection": [],
    "grounding": [],
    "answer_quality": [],
    "retrieval": [],
  }
  for failure in failures:
    checks = failure.get("checks", {})
    case_id = failure["id"]
    if not checks.get("route_ok"):
      buckets["routing"].append(case_id)
    if checks.get("expected_tool") and not checks.get("tool_ok"):
      buckets["tool_selection"].append(case_id)
    if not checks.get("grounding_ok"):
      buckets["grounding"].append(case_id)
    if not checks.get("answer_ok"):
      buckets["answer_quality"].append(case_id)
    if checks.get("relevant_terms") and not checks.get("retrieval_ok"):
      buckets["retrieval"].append(case_id)
  return {key: value for key, value in buckets.items() if value}


def _render_markdown(payload: dict) -> str:
  retrieval = payload["retrieval"]
  generation = payload["generation"]
  failures = payload["failure_analysis"]
  passed = sum(1 for case in payload["cases"] if case["passed"])

  lines = [
    "# Evaluation Results",
    "",
    f"Generated: {payload['generated_at']}",
    "",
    "## Summary",
    "",
    f"- Cases passed: **{passed}/{payload['case_count']}**",
    f"- Retrieval hit rate@3: **{retrieval['hit_rate']:.3f}**",
    f"- Retrieval MRR: **{retrieval['mrr']:.3f}**",
    f"- Route accuracy: **{generation['route_accuracy']:.3f}**",
    f"- Tool accuracy: **{generation['tool_accuracy']:.3f}**",
    f"- Grounding accuracy: **{generation['grounding_accuracy']:.3f}**",
    f"- Clarification accuracy: **{generation['clarification_accuracy']:.3f}**",
    f"- Overall success rate: **{generation['overall_success_rate']:.3f}**",
    "",
    "## Failure Analysis",
    "",
  ]

  if failures:
    for mode, case_ids in failures.items():
      lines.append(f"- **{mode.replace('_', ' ').title()}**: {', '.join(case_ids)}")
  else:
    lines.append("- No failures in the current eval set.")

  lines.extend(
    [
      "",
      "## What the failures teach us",
      "",
      "- Routing failures usually mean intent heuristics need tighter phrase patterns.",
      "- Tool failures indicate the assistant answered from retrieval instead of invoking structured tools.",
      "- Grounding failures mean the answer omitted catalogue-backed SKU, price, or stock evidence.",
      "- Multi-turn failures often come from lost slot memory or follow-up guardrails treating context-poor pricing queries as out of domain.",
      "",
      "## How to rerun",
      "",
      "```bash",
      "python -m eval.run_eval",
      "```",
      "",
      "Machine-readable output is written to `eval/results.json`.",
    ]
  )
  return "\n".join(lines)


if __name__ == "__main__":
  main()
