# Architecture — Audit Mind AI

## 1. Overview

Audit Mind AI is a **state graph (LangGraph)** where each node is a stage of the
audit. The state is shared and accumulated throughout the flow. The audit phase
delegates to **ReAct sub-agents** (one per dimension, running in parallel), which
explore the code with read-only tools; their findings are then checked against the
code on disk (and optionally by an adversarial LLM judge) before the report.

```
                    ┌──────────────┐
      START ───────▶│  discovery   │  scans the project, detects stack + inventory
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │plan_questions│  LLM generates clarification questions
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │   clarify    │  ⏸ interrupt → user responds (human-in-the-loop)
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │   planning   │  LLM selects applicable dimensions
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐  per dimension, in a thread pool:
                    │    audit     │   1) create_react_agent(tools) → text report
                    └──────┬───────┘   2) with_structured_output → DimensionResult
                           ▼
                    ┌──────────────┐
                    │    verify    │  deterministic evidence check on disk (no LLM)
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │ adversarial  │  skeptical LLM judge (optional, off by default)
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │  synthesis   │  health score + executive summary
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │    report    │  Markdown + HTML + SARIF → disk
                    └──────┬───────┘
                           ▼
                          END
```

Entry points: **CLI** (`auditor audit`, `MemorySaver`) and **API** (`auditor serve`,
FastAPI + SSE, `SqliteSaver`). The API only answers loopback `Host`s (`api/security.py`, AD-002);
on startup it marks orphaned audits `interrupted`, and `AuditRunner(resume=True)` continues them
from the last checkpoint (pending interrupt → re-ask; pending nodes → `stream(None)`). The Vite/React frontend in `frontend/` consumes the API.

## 2. Components

| Module | Responsibility |
| --- | --- |
| `config.py` | Settings via `pydantic-settings` (env / `.env` / `~/.config/auditor/.env`); provider → credential/package maps. |
| `llm.py` | Multi-provider factory (`init_chat_model`), memoized per `(provider, model, params)`; per-audit override. |
| `logging_config.py` | Idempotent logging setup (`AUDITOR_LOG_LEVEL`). |
| `state.py` | `AuditState` (TypedDict + reducers) and Pydantic domain models. |
| `tools/project.py` | Stack detection and inventory construction. |
| `tools/filesystem.py` | Scoped read-only tools (read/list/search). |
| `prompts/templates.py` | All prompts, centralized (persona, investigator, structuring, judge lenses). |
| `nodes/*` | One file per graph node. |
| `graph.py` | Graph assembly and compilation. |
| `report/renderer.py` · `report/sarif.py` | Markdown/HTML (Jinja2, autoescape) and SARIF 2.1.0. |
| `cli.py` | Terminal interface (Typer + Rich) and interrupt loop. |
| `api/*` | FastAPI routes, background runner (thread per audit), SQLite store, schemas, retention (delete/compact). |

## 3. Graph state

`AuditState` is a `TypedDict`. Fields with _reducers_:

- `messages: Annotated[list, add_messages]` — conversation history (currently unused by nodes).
- `dimension_summaries: Annotated[list, operator.add]` — accumulates summaries.

`findings` is **not** additive: `audit` writes it, and `verify`/`adversarial` overwrite it
with the filtered list. All other fields are last-write-wins. Enums (e.g., `Severity`) are
serialized via `model_dump(mode="json")` to keep the state JSON-serializable and compatible
with persistent checkpointers. `provider`/`model` live in the state so concurrent audits can
use different LLMs.

## 4. Human-in-the-loop

The `clarify` node calls `interrupt(payload)`. Because `interrupt` **re-executes
the node from the beginning** when resuming, question generation (which makes an
LLM call) is isolated in the preceding `plan_questions` node, avoiding duplicate
calls. Resumption occurs via `Command(resume=answers)` — from the CLI prompt loop or
from `POST /audits/{id}/answers` in the API.

A **checkpointer** is mandatory for `interrupt`. The CLI uses `MemorySaver`; the API uses
`SqliteSaver` (`~/.config/auditor/audits-checkpoints.sqlite`).

Sub-agents are created with `checkpointer=False` (decision AD-001 in `.specs/STATE.md`): only the
top-level graph is checkpointed. Audits are deleted manually (`DELETE /audits/{id}` →
`auditor.api.retention.delete_audit`: reports → checkpoints → metadata), and `auditor db compact`
removes legacy sub-graph checkpoints.

## 5. ReAct sub-agents (audit phase)

Each dimension is audited in two decoupled phases:

1. **Investigation** — `create_react_agent(llm, tools, prompt)` with **no** `response_format`.
   Tools: `read_file`, `list_directory`, `search_code`. The agent ends by writing a textual report.
2. **Structuring** — a separate `llm.with_structured_output(DimensionResult)` call receives only
   the report text (`STRUCTURE_PROMPT`), not the tool-call history. This avoids the
   structured-output step re-sending the whole tool history and the related boundary errors.

- **Parallelism:** investigators run in a `ThreadPoolExecutor`
  (`AUDITOR_MAX_CONCURRENT_INVESTIGATORS`, default 4). SSE/console progress is emitted from the
  main thread (where the LangGraph stream writer is valid); aggregation follows the plan order.
- **`recursion_limit`:** `AUDITOR_MAX_INVESTIGATOR_STEPS` (default 80) — graph steps, roughly
  half of that in tool calls.
- **Failure isolation:** an exception in one dimension is recorded in its summary without
  aborting the others.

## 6. Evidence verification and adversarial judge

- `verify` (no LLM): the cited file must exist inside the root and the `evidence` snippet must
  appear in it (tolerant matching). Unsubstantiated findings are **dropped**; findings without
  file/evidence are kept with `confidence ≤ 0.5`.
- `adversarial` (optional): for findings with a file and severity ≥ threshold, a skeptical judge
  reads the real code window and tries to refute them (1–3 lenses, majority vote). Refuted →
  dropped; uncertain → confidence lowered.

## 7. Tool safety

`_safe_resolve` resolves paths (following symlinks) under the root and rejects any target
outside it (path traversal, e.g., `../../etc/passwd`). All three tools enforce it: `search_code`
additionally rejects absolute globs or globs with a `..` component and skips files whose real
path (symlink target) is outside the root. Binary files and files above `AUDITOR_MAX_FILE_BYTES`
are skipped; build/dependency directories (`node_modules`, `.git`, `venv`, …) are ignored,
matched against the path **relative** to the root (regression tests: `tests/test_tools_scoping.py`).

## 8. Health score

`compute_health_score` starts at 100 and subtracts weights by severity
(`critical=40, high=20, medium=8, low=3, info=0`), with a floor of 0. It is a
heuristic indicator for executive reading, not a formal metric.

## 9. Data flow (summary)

```
project_path (+ provider, model, user_goal)
  → stack_profile + inventory          (discovery)
  → clarifying_questions               (plan_questions)
  → user_context                       (clarify)
  → plan.dimensions + focus_notes      (planning)
  → findings[] + dimension_summaries   (audit)
  → findings[] (filtered) + verification   (verify)
  → findings[] (filtered) + adversarial    (adversarial)
  → health_score + executive_summary   (synthesis)
  → report_{markdown,html,sarif}_path  (report)
```
