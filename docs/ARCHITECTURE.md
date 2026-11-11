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
                    │    audit     │   1) create_agent(tools, budget middleware) → text report
                    └──────┬───────┘   2) with_structured_output → DimensionResult
                           ▼
                    ┌───────────────┐
                    │dependency_scan│ lockfiles → OSV.dev, runtime → endoflife.date (opt-in, no LLM)
                    └──────┬────────┘
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
| `events.py` | Single `emit` (LangGraph custom stream) + `NODE_LABELS`/`NODE_ICONS` shared by nodes, API and CLI. |
| `scoring.py` | Health score + severity counting (with/without zeros) shared by synthesis, report, CLI and API. |
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

1. **Investigation** — `langchain.agents.create_agent(llm, tools, system_prompt, middleware=[budget])` with **no** `response_format`.
   Tools: `read_file`, `list_directory`, `search_code`. The agent ends by writing a textual report.
2. **Structuring** — a separate `llm.with_structured_output(DimensionResult)` call receives only
   the report text (`STRUCTURE_PROMPT`), not the tool-call history. This avoids the
   structured-output step re-sending the whole tool history and the related boundary errors.

- **Parallelism:** investigators run in a `ThreadPoolExecutor`
  (`AUDITOR_MAX_CONCURRENT_INVESTIGATORS`, default 4). SSE/console progress is emitted from the
  main thread (where the LangGraph stream writer is valid); aggregation follows the plan order.
- **Step budget (G32/G44):** `AUDITOR_MAX_INVESTIGATOR_STEPS` (default 80, ≈ 2 per tool call) gives
  `max(2, steps // 2)` model calls. A `_BudgetMiddleware` counts model calls (the `AIMessage`s in the
  history): on the last 2 calls `wrap_model_call` appends a wrap-up notice; when the budget is spent
  `before_model` ends the run with our own `BUDGET_EXHAUSTED_MARKER` (`jump_to="end"`). `recursion_limit`
  (`4 × calls + 10`) is only a safety net — in `create_agent` hitting it raises `GraphRecursionError`
  and loses the history. On the marker, one **salvage** call without tools writes the report from a
  condensed transcript (tool results ≤ 2 000 chars each, ≤ 60 000 total, inside `<historico>`
  delimiters as untrusted data); the dimension summary is prefixed `⚠️ Investigação parcial…` and the
  SSE event status is `partial`.
- **Failure isolation:** an exception in one dimension is recorded in its summary without
  aborting the others.

## 6. Evidence verification and adversarial judge

- `verify` (no LLM): the cited file must exist inside the root and the `evidence` snippet must
  appear in it (tolerant matching). Unsubstantiated findings are **dropped**; findings without
  file/evidence are kept with `confidence ≤ 0.5`.
- `adversarial` (optional, parallel up to `AUDITOR_MAX_CONCURRENT_INVESTIGATORS`; aggregation in input
  order): for findings with a file and severity ≥ threshold, a skeptical judge
  reads the real code window and tries to refute them (1–3 lenses, majority vote). Refuted →
  dropped; uncertain → confidence lowered.

## 6.1 Dependency scan (G48, opt-in)

`auditor.vulnscan`: lockfile parsers (Strategy + registry), runtime detectors, `OSVClient` /
`EndOfLifeClient` gateways (fixed HTTPS hosts, 15 s timeout, 5 MB streaming cap, failures recorded
— never raised) and `scanner.scan` (facade). The `dependency_scan` node runs after `audit` (which
overwrites `findings`) and appends deterministic findings (`source="osv"|"endoflife"`) citing the
exact lockfile line, so `verify` confirms them; `adversarial` skips them (`is_deterministic`).
Disabled → no HTTP client is created (AD-003). Stats go to `state["dependency_scan"]`, the SSE
event `dependency_scan` and the report's explicit status line.

## 7. Tool safety

`_safe_resolve` resolves paths (following symlinks) under the root and rejects any target
outside it (path traversal, e.g., `../../etc/passwd`). All three tools enforce it: `search_code`
additionally rejects absolute globs or globs with a `..` component and skips files whose real
path (symlink target) is outside the root. Binary files and files above `AUDITOR_MAX_FILE_BYTES`
are skipped; build/dependency directories (`node_modules`, `.git`, `venv`, …) are ignored,
matched against the path **relative** to the root (regression tests: `tests/test_tools_scoping.py`).
`search_code` walks with `os.walk(followlinks=False)`, pruning ignored dirs before listing them (and,
for globs without `**`, anything deeper than the pattern), and matches globs per segment — on a tree
with 20 000 files in `node_modules`, `**/*` went from ~2.4 s to ~7 ms per call (G34).

## 8. Health score

`compute_health_score` starts at 100 and subtracts weights by severity
(`critical=40, high=20, medium=8, low=3, info=0`), with a floor of 0. It is a
heuristic indicator for executive reading, not a formal metric.

Vulnerable-package findings (`source == "osv"`, set only by the dependency scanner) are summed
as a group capped at `DEPENDENCY_PENALTY_CAP = 40` (G49), so enabling the scan cannot zero the
score on its own; runtime (`endoflife`) and LLM findings keep their full weight. `synthesis`
stores the breakdown (`dependency_penalty`: applied/uncapped/packages) next to `health_score`, and
the Markdown/HTML report, CLI summary, synthesis prompt and report chat render the line
`Pacotes vulneráveis (OSV): −N pontos (K pacote(s))` from that stored value (never recomputed, so
audits finished before G49 show no line).

## 9. Data flow (summary)

```
project_path (+ provider, model, user_goal)
  → stack_profile + inventory          (discovery)
  → clarifying_questions               (plan_questions)
  → user_context                       (clarify)
  → plan.dimensions + focus_notes      (planning)
  → findings[] + dimension_summaries   (audit)
  → findings[] (+osv/endoflife) + dependency_scan   (dependency_scan, opt-in)
  → findings[] (filtered) + verification   (verify)
  → findings[] (filtered) + adversarial    (adversarial)
  → health_score + dependency_penalty + executive_summary   (synthesis)
  → report_{markdown,html,sarif}_path  (report)
```
