# Frontend & API Spec — Audit Mind AI

Architecture specification for a web interface on top of the existing agent, in
**local/desktop mode** (single user, no dedicated server).

> ⚠️ **Superseded in part — implementation note (2026).** This document was written
> around a **Next.js** frontend. The API layer described here was delivered and is
> current, but the **frontend was implemented with Vite + React** in `frontend/`
> (dev server on **:5173**, proxying the API on **:8020**), not Next.js in `web/`.
> The Next.js-specific sections below (App Router, port 3020, `web/` tree) are the
> original design and no longer match the code. See `README.md` / `DOCUMENTACAO.md`
> for the current setup.

---

## 1. Objectives and constraints

- **Reuse the core:** the LangGraph graph (`src/auditor`) does not change; the API
  is just one more entry layer, alongside the CLI.
- **Local/desktop:** backend and frontend run on `localhost`, single user. No
  multi-tenant, no login. Simplicity > scalability.
- **Secret security:** the LLM provider key lives **only in the backend**
  (`.env` / `~/.config/auditor/.env`) and **never** travels to the browser.
- **Rich experience:** findings dashboard (severities, filters), live progress,
  and clarifications chat.

### Non-objectives (v1)
- Authentication/users, multi-tenant, billing.
- Remote execution / distributed queue.
- Packaging as a native app (Electron/Tauri) — considered in §10.

---

## 2. Architecture

```
┌─────────────────────────────┐        ┌───────────────────────────────┐
│  Frontend (Next.js/React)   │        │  Backend (FastAPI, localhost)  │
│                             │  HTTP  │                               │
│  • New audit (form)         │ ─────► │  POST /audits                 │
│  • Live progress            │  SSE   │  GET  /audits/{id}/stream     │
│  • Clarifications chat       │ ◄───── │  POST /audits/{id}/answers    │
│  • Report dashboard         │        │  GET  /audits/{id}/report     │
│                             │        │  GET  /providers              │
└─────────────────────────────┘        └───────────────┬───────────────┘
        localhost:3020                                  │ invokes
                                                        ▼
                                        ┌───────────────────────────────┐
                                        │  Core — LangGraph graph        │
                                        │  (discovery→clarify→audit→…)   │
                                        │  Checkpointer: SqliteSaver     │
                                        └───────────────────────────────┘
```

- **Backend:** FastAPI + Uvicorn on `127.0.0.1:8010`. Reuses `build_graph()`.
- **Frontend:** Next.js (App Router) on `127.0.0.1:3020`, consuming the API via
  `fetch` + `EventSource` (SSE).
- **Persistence:** `SqliteSaver` (file `~/.config/auditor/audits.sqlite`) for the
  graph state (allows pausing at the `interrupt` and resuming between requests and
  even after a backend restart). Audit metadata (list/history) in the same
  database.

---

## 3. API design (FastAPI)

### 3.1 Endpoints

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/providers` | Lists supported providers (reuses `PROVIDER_PACKAGE`). |
| `POST` | `/audits` | Creates and starts an audit. Returns `{id, status}`. |
| `GET` | `/audits` | Lists audits (local history). |
| `GET` | `/audits/{id}` | Current state + summary (health score, count by severity). |
| `GET` | `/audits/{id}/stream` | **SSE**: progress, clarification, and completion events. |
| `POST` | `/audits/{id}/answers` | Sends clarification answers → resumes the graph. |
| `GET` | `/audits/{id}/findings` | Structured findings (JSON) for the dashboard. |
| `GET` | `/audits/{id}/report?format=html\|md` | Rendered report. |
| `DELETE` | `/audits/{id}` | Removes the audit and artifacts. |

### 3.2 Schemas (Pydantic — reused from the core)

```jsonc
// POST /audits  (request)
{
  "project_path": "/home/joao/proj",
  "goal": "Pre-production security review",      // optional
  "provider": "deepseek",                        // optional (overrides .env)
  "model": "deepseek-chat",                      // optional
  "interactive": true                            // if false, skips clarifications
}

// POST /audits/{id}/answers  (request)
{ "answers": { "Production environment?": "yes, critical production" } }
```

Findings already exist as `Finding` (Pydantic) in the core — the `/findings`
endpoint serializes `state["findings"]` directly (no new renderer).

### 3.3 Streaming (SSE) — the central point

The backend runs the graph in a **background task** per audit and publishes
events to an in-memory queue; `GET /stream` drains the queue (with replay of
events that already occurred, for reconnection). SSE event types:

| `event` | `data` | When |
| --- | --- | --- |
| `phase` | `{node, label, status}` | Start/end of each node (discovery, planning, …). |
| `investigator` | `{dimension, status, findings_count}` | Per-dimension progress in the audit phase. |
| `clarification` | `{questions:[{question, rationale}]}` | Graph reached the `interrupt`; front opens the chat. |
| `finding` | `{dimension, title, severity, …}` | (Optional) finding emitted in real time. |
| `completed` | `{health_score, counts, report_url}` | Audit completed. |
| `error` | `{message}` | Failure. |

**Granular per-investigator progress:** today the `audit` node processes all
dimensions internally (it would emit only one event in `stream_mode="updates"`).
For the front to receive per-dimension progress, the `audit` node must emit
events via the **LangGraph stream writer** (`get_stream_writer()` /
`stream_mode="custom"`). This is the only relevant change in the core (small and
optional).

### 3.4 Human-in-the-loop (interrupt) flow on the web

```
Frontend                         Backend                        Graph
   │  POST /audits                  │                              │
   │ ─────────────────────────────►│  creates thread_id, bg task─►│ discovery…
   │  GET /stream (opens SSE)       │                              │
   │ ◄──── phase(discovery) ────────│ ◄────────────────────────────│
   │ ◄──── clarification(questions)─│ ◄── interrupt() ─────────────│ (pauses)
   │  [user answers in the chat]    │                              │
   │  POST /answers ───────────────►│  Command(resume=answers) ───►│ (resumes)
   │ ◄──── phase(planning/audit) ───│ ◄────────────────────────────│
   │ ◄──── completed ───────────────│ ◄────────────────────────────│ END
```

The `SqliteSaver` ensures the state survives while waiting for the answer (the
background task waits on an `asyncio.Event` until `/answers` arrives).

### 3.5 CORS and local security
- CORS restricted to `http://localhost:3020` / `127.0.0.1:3020`.
- Backend listens **only** on `127.0.0.1` (does not expose to the network).
- `project_path` is read from the local disk — acceptable for a single-user tool;
  the tools remain **read-only**. Validate that the path exists and is a directory.
- The LLM key never goes to the browser; `GET /providers` reports only
  names/required credential, not values.

---

## 4. Frontend design (Next.js)

### 4.1 Screens

1. **New Audit** — form: project path, goal, provider/model (dropdown from
   `/providers`), "ask clarification questions" toggle.
2. **Run (live)** — timeline of phases + list of investigators per dimension with
   status; opens a **chat panel** when a `clarification` arrives.
3. **Report (dashboard)** — header with **health score** and distribution by
   severity; filterable list of findings (by dimension/severity), each one
   expandable (description, evidence, recommendation, file:line); export buttons
   (HTML/MD/JSON); executive summary.
4. **History** — list of previous audits (from `GET /audits`).

### 4.2 Wireframes (ASCII)

```
┌── New Audit ──────────────────────────────────┐
│ Path:     [/home/joao/proj............] [📁]  │
│ Goal:     [Pre-production review...........]  │
│ Provider: [deepseek ▾]  Model: [deepseek-chat] │
│ [x] Ask clarification questions                │
│                                  [ Start audit ]
└───────────────────────────────────────────────┘

┌── Run ────────────────────────────────────────┐
│ ✓ Discovery       ✓ Planning                   │
│ ⏳ Audit                                        │
│    ✓ security   (5)   ⏳ quality   … perf …     │
│ ┌ Clarifications ────────────────────────────┐ │
│ │ 1. Production environment? [_________] [ok] │ │
│ └─────────────────────────────────────────────┘│
└───────────────────────────────────────────────┘

┌── Report ─────────────────────────────────────┐
│  Health: 62/100  ● crit 1  ● high 3  ● med 5   │
│  Filters: [dimension ▾] [severity ▾]  [export] │
│  ┌ [CRITICAL] Hardcoded secret  app.py:16  ▸ │ │
│  ┌ [HIGH]     XSS in the report  renderer  ▸ │ │
└───────────────────────────────────────────────┘
```

### 4.3 Frontend tech stack
- **Next.js (App Router) + TypeScript**.
- **TanStack Query** for data; **EventSource** (SSE) for the stream.
- **Tailwind CSS** + components (shadcn/ui) for the dashboard.
- Markdown rendering (react-markdown) for the executive summary.
- No heavy global state; a lightweight store (Zustand) for the active audit.

---

## 5. Proposed directory structure

```
auditor-IA/
├── src/auditor/            # core (existing) — unchanged, except stream writer in audit
│   └── api/                # NEW: FastAPI
│       ├── main.py         # app, CORS, routes
│       ├── routes.py       # endpoints
│       ├── streaming.py    # task management + SSE queue
│       ├── schemas.py      # request/response models
│       └── store.py        # SqliteSaver + metadata
├── web/                    # NEW: Next.js frontend
│   ├── app/                # routes (new, run, report, history)
│   ├── components/
│   └── lib/api.ts          # API client + SSE
└── pyproject.toml          # + optional extra [api] (fastapi, uvicorn, sse-starlette)
```

New extra in `pyproject.toml`:
```toml
api = ["fastapi>=0.115", "uvicorn[standard]>=0.30", "sse-starlette>=2.1"]
```

---

## 6. Local run experience

A `Makefile` target brings up both parts:

```makefile
api:   ; . .venv/bin/activate && uvicorn auditor.api.main:app --host 127.0.0.1 --port 8010
web:   ; cd web && npm run dev
dev:   ; make -j2 api web        # backend + frontend together
```

User flow: `make dev` → open `http://localhost:3020`.

---

## 7. Required core changes (minimal)

1. **Stream writer in the `audit` node** — emit per-dimension events
   (`get_stream_writer()`), preserving the current CLI behavior. **The only
   essential code change.**
2. **Configurable checkpointer** — `build_graph()` already accepts a
   `checkpointer`; the API passes a `SqliteSaver`. No refactor.
3. **JSON export of findings** — trivial: serialize `state["findings"]` (already dicts).

Nothing in the audit flow itself changes — the core remains interface-agnostic.

---

## 8. Phased implementation plan

| Phase | Deliverable | Depends on |
| --- | --- | --- |
| **F1 — Base API** | `/providers`, `/audits` (start), `/audits/{id}`, `/report` (`--no-questions` mode); SqliteSaver | core |
| **F2 — Streaming** | Phase SSE + per-dimension stream writer in the `audit` node | F1 |
| **F3 — Human-in-the-loop** | `clarification` via SSE + `POST /answers` (resume) | F2 |
| **F4 — Frontend MVP** | New Audit + Run + Report screens | F1–F3 |
| **F5 — Dashboard & history** | Filters, export, history screen | F4 |
| **F6 — Polish** | Errors, SSE reconnection, empty states, responsive | F5 |

Navigable MVP ≈ F1→F4.

---

## 9. Risks and open decisions

- **Per-dimension progress** requires the stream writer (otherwise progress stays
  "coarse", only per node). Recommended to implement in F2.
- **Long audits**: define a timeout/token limit per audit and clear cost feedback
  (we already have limits in `config`).
- **SSE reconnection**: keep the replay of events per audit (in-memory buffer +
  state in SQLite) so the front can reconnect without losing progress.
- **`project_path` security**: local/single-user makes it acceptable to read any
  path; if it ever becomes multi-user, this needs a sandbox/allowlist.

---

## 10. Future evolution (out of v1 scope)
- Package as a desktop app (Tauri/Electron) for distribution without a terminal.
- Authentication + per-user history (path toward the "web app" scenario).
- WebSocket instead of SSE if a need for intensive bidirectional communication arises.
- "Chat with the report" (questions about the findings after the audit).
```
