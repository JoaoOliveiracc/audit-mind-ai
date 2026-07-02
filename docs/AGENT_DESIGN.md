# Agent Design & Decisions — Audit Mind AI

This document records the design decisions and how they reflect **LangChain/LangGraph
best practices**.

## 1. Why LangGraph (and not a monolithic AgentExecutor)?

Auditing is a process with **distinct stages, clear dependencies, and a single point of
human interaction**. LangGraph models this as an explicit state graph, which brings:

- **Deterministic flow control** — the discovery → clarification →
  plan → audit → synthesis → report order is guaranteed by the graph's edges.
- **Native human-in-the-loop** — `interrupt`/`Command(resume=...)` with a checkpointer.
- **Observability** — each node is an inspectable step (`stream_mode="updates"`).
- **Resumption** — with a persistent checkpointer, an audit can be paused and resumed.

A generic `AgentExecutor` would be opaque and hard to pause for conversation.

## 2. "Orchestrator + investigators" pattern

The main graph is the **orchestrator**; the audit phase delegates to specialized
**ReAct sub-agents** (one per dimension). This is the
*supervisor/worker* pattern:

- Each investigator has a **focused prompt** and the **same set of tools**.
- The separation avoids a single giant prompt trying to cover everything (which degrades quality).
- It makes adding/removing dimensions easy without touching the rest of the graph.

## 3. Structured output instead of text parsing

All decision points use **Pydantic structured output**:

- `with_structured_output(ClarifyingQuestions)` — clarification questions.
- `with_structured_output(AuditPlan)` — dimension selection.
- `create_react_agent(..., response_format=DimensionResult)` — findings.

Advantages: automatic validation, provider retries on invalid schema,
zero fragile string parsing. It is LangChain's current recommended practice.

## 4. Read-only and safe tools

- The agent **audits, it does not fix** → all tools are read-only.
- Scope restricted to the project root with **path traversal blocking**.
- Size/quantity limits → cost and latency control.

This follows the principle of **least privilege** for agent tools.

## 5. Centralized and versionable prompts

All prompts live in `prompts/templates.py`, separated from the logic. This allows
iterating on prompt engineering without changing orchestration code and makes review easier.

Principles built into the persona (`SYSTEM_PERSONA`):
- **Evidence required** — reduces hallucination ("if you did not verify it, do not assert it").
- **Precision > volume** — avoids inflating the report with speculative findings.
- **Always actionable** — every finding requires a recommendation.

## 6. Determinism and reproducibility

Default temperature `0`. Audits should be as reproducible as possible;
creative variability is not desirable here.

## 7. Robustness

- A single investigator's failure is **isolated** (try/except per dimension).
- Dimension validation against the enum, with a _fallback_ to a default set.
- JSON-safe serialization of the state (compatible with persistent checkpointers).
- Recursion limits on the sub-agents (avoids infinite tool-calling loops).

## 8. Deliberately deferred decisions (trade-offs)

| Decision | v0.1 | Why | Evolution |
| --- | --- | --- | --- |
| Dimension parallelism | Sequential | Cost predictability and readable logs | *Send API* (ROADMAP) |
| Checkpointer | `MemorySaver` | Simplicity | `SqliteSaver`/`Postgres` |
| External scanners | Absent | Keep zero toolchain dependency | Optional integration |
| Multi-provider | ✅ via `init_chat_model` | Flexibility without provider lock-in | Per-provider presets |

## 9. Extensibility

- **New dimension:** add it to the `AuditDimension` enum and to `DIMENSION_GUIDANCE`. The
  planner will then consider it automatically.
- **New tool:** add it in `make_project_tools` — every investigator receives it.
- **New report format:** add a renderer in `report/` and call it in `report_node`.
- **Another LLM:** set `AUDITOR_PROVIDER`/`AUDITOR_MODEL` (or `--provider`/`--model`).
  The factory in `llm.py` uses `init_chat_model`, so any provider supported
  by LangChain works without code changes — just install the package.

## 10. Best practices applied (checklist)

- [x] Explicit graph with typed state and reducers.
- [x] Human-in-the-loop with `interrupt` + checkpointer.
- [x] Isolation of question generation from the interruption point (avoids double calls).
- [x] Pydantic structured output at every decision point.
- [x] ReAct sub-agents with tools and `response_format`.
- [x] Least-privilege tools (read-only, scoped).
- [x] Centralized and versionable prompts.
- [x] Externalized configuration (12-factor).
- [x] Per-stage failure handling.
- [x] Offline tests that do not depend on the LLM.
