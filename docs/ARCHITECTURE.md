# Architecture — Audit Mind AI

## 1. Overview

Audit Mind AI is a **state graph (LangGraph)** where each node is a stage of the
audit. The state is shared and accumulated throughout the flow. The audit phase
delegates to **ReAct sub-agents** (one per dimension), which explore the code
with read-only tools and return structured findings.

```
                    ┌─────────────┐
      START ───────▶│  discovery  │  scans the project, detects stack + inventory
                    └──────┬──────┘
                           ▼
                    ┌──────────────┐
                    │plan_questions│ LLM generates clarification questions
                    └──────┬───────┘
                           ▼
                    ┌─────────────┐
                    │   clarify   │ ⏸ interrupt → user responds (human-in-the-loop)
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │  planning   │ LLM selects applicable dimensions
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐   for each dimension:
                    │    audit    │   create_react_agent(tools) → DimensionResult
                    └──────┬──────┘   (read_file, list_directory, search_code)
                           ▼
                    ┌─────────────┐
                    │  synthesis  │ health score + executive summary
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │   report    │ Markdown + HTML → disk
                    └──────┬──────┘
                           ▼
                          END
```

## 2. Components

| Module | Responsibility |
| --- | --- |
| `config.py` | Settings via `pydantic-settings` (env / `.env`). |
| `llm.py` | Memoized `ChatAnthropic` factory. |
| `state.py` | `AuditState` (TypedDict + reducers) and Pydantic domain models. |
| `tools/project.py` | Stack detection and inventory construction. |
| `tools/filesystem.py` | Scoped read-only tools (read/list/search). |
| `prompts/templates.py` | All prompts, centralized. |
| `nodes/*` | One file per graph node. |
| `graph.py` | Graph assembly and compilation. |
| `report/renderer.py` | Markdown and HTML rendering (Jinja2). |
| `cli.py` | Terminal interface (Typer + Rich) and interrupt loop. |

## 3. Graph state

`AuditState` is a `TypedDict` with annotated _reducers_:

- `messages: Annotated[list, add_messages]` — conversation history.
- `findings: Annotated[list, operator.add]` — accumulates findings.
- `dimension_summaries: Annotated[list, operator.add]` — accumulates summaries.

The remaining fields are replaced by direct assignment (last write wins).
Enums (e.g., `Severity`) are serialized to string via `model_dump(mode="json")`
to keep the state JSON-serializable and compatible with persistent checkpointers.

## 4. Human-in-the-loop

The `clarify` node calls `interrupt(payload)`. Because `interrupt` **re-executes
the node from the beginning** when resuming, question generation (which makes an
LLM call) was isolated in the preceding `plan_questions` node, avoiding duplicate
calls. Resumption occurs via `Command(resume=answers)` triggered by the CLI.

A **checkpointer** is mandatory for `interrupt` to work. v0.1 uses `MemorySaver`
(in memory). For persistence across runs, swap it for
`SqliteSaver`/`PostgresSaver` in `build_graph`.

## 5. ReAct sub-agents (audit phase)

Each dimension is audited by an agent created with `create_react_agent`:

- **Tools:** `read_file`, `list_directory`, `search_code` (scoped to the root).
- **`response_format=DimensionResult`:** forces structured output validated by Pydantic.
- **`recursion_limit`:** limits the reasoning steps (env `AUDITOR_MAX_INVESTIGATOR_STEPS`).
- **Failure isolation:** an exception in one dimension is caught and recorded, without aborting the others.

> **Evolution note:** the investigators run sequentially in v0.1 for cost
> predictability. Parallelization via LangGraph's *Send API* is mapped out in the
> ROADMAP.

## 6. Tool safety

`_safe_resolve` resolves paths under the root and rejects any target outside it
(protection against path traversal, e.g., `../../etc/passwd`). Binary files and
files above `AUDITOR_MAX_FILE_BYTES` are ignored. Build/dependency directories
(`node_modules`, `.git`, `venv`, etc.) are skipped during the scan.

## 7. Health score

`compute_health_score` starts at 100 and subtracts weights by severity
(`critical=40, high=20, medium=8, low=3, info=0`), with a floor of 0. It is a
heuristic indicator for executive reading, not a formal metric.

## 8. Data flow (summary)

```
project_path
  → stack_profile + inventory        (discovery)
  → clarifying_questions             (plan_questions)
  → user_context                     (clarify)
  → plan.dimensions                  (planning)
  → findings[] + dimension_summaries (audit)
  → health_score + executive_summary (synthesis)
  → report_markdown_path + report_html_path (report)
```
