# Evaluation Results

Generated: 2026-06-23T23:24:40.235123+00:00

## Summary

- Cases passed: **20/20**
- Retrieval hit rate@3: **0.778**
- Retrieval MRR: **0.778**
- Route accuracy: **1.000**
- Tool accuracy: **1.000**
- Grounding accuracy: **1.000**
- Clarification accuracy: **1.000**
- Overall success rate: **1.000**

## Failure Analysis

- No failures in the current eval set.

## What the failures teach us

- Routing failures usually mean intent heuristics need tighter phrase patterns.
- Tool failures indicate the assistant answered from retrieval instead of invoking structured tools.
- Grounding failures mean the answer omitted catalogue-backed SKU, price, or stock evidence.
- Multi-turn failures often come from lost slot memory or follow-up guardrails treating context-poor pricing queries as out of domain.

## How to rerun

```bash
python -m eval.run_eval
```

Machine-readable output is written to `eval/results.json`.