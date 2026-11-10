# Roadmap — Audit Mind AI

## v0.1 (current) ✅
- Complete LangGraph graph (discovery → clarify → planning → audit → synthesis → report).
- Human-in-the-loop via `interrupt`.
- ReAct investigators per dimension with structured output.
- Agnostic stack detection.
- Safe, read-only tools.
- Markdown + HTML report.
- Interactive CLI (Typer + Rich).
- Offline smoke tests.

## v0.1.x — Hardening (from the 2026-11-10 analysis)
- [x] Enforce root scoping in `search_code` (glob `..`, symlinks) and fix ancestor `ignore_dirs` matching (G25/G26/G30).
- [ ] Reconcile/resume orphaned audits after API restart; `Host` validation against DNS rebinding (G31/G27).
- [ ] Investigator step budget with forced final report; text extraction in synthesis (G32/G33).
- [ ] CI (lint, tests, type-check, frontend build) and mypy clean (G37/G38).

See `DOCUMENTACAO.md` §10.3 for the full list (G25–G43).

## v0.2 — Scale and performance
- [x] **Parallelize investigators** — delivered with a thread pool (`AUDITOR_MAX_CONCURRENT_INVESTIGATORS`).
- [x] **Persistent checkpointer** (`SqliteSaver`) — delivered in the API mode.
- [x] Stop persisting sub-agent checkpoints; manual deletion + `auditor db compact` (G28/G29).
- [ ] Migrate investigators from deprecated `create_react_agent` to `langchain.agents.create_agent` (G44).
- [ ] Cache file reads across dimensions.
- [ ] Intelligent summarization/selection of files in very large projects (map-reduce).

## v0.3 — Analysis depth
- [ ] Optional integration with external scanners (Semgrep, Trivy, gitleaks, pip-audit/npm-audit).
- [ ] Reconciliation: scanner findings + LLM findings, with deduplication.
- [x] Deterministic evidence verification (`verify` node) — delivered.
- [x] Adversarial verification of findings (skeptical LLM judge, `adversarial` node) — delivered (opt-in).
- [ ] Git history analysis (hotspots, authors, churn).

## v0.4 — Experience and integration
- [x] API layer (FastAPI) reusing the same graph — **delivered (F1–F3)**: endpoints, SSE, SQLite checkpointer and human-in-the-loop. See [`FRONTEND_SPEC.md`](FRONTEND_SPEC.md).
- [x] Structured JSON export of findings — **delivered** (`GET /audits/{id}/findings`).
- [x] Web frontend (Vite + React) — **MVP delivered (F4)**: new audit, live execution (SSE) and findings dashboard. In `frontend/` (migrated from the original Next.js `web/`, now removed).
- [ ] Frontend F5–F6: rich history, robust SSE reconnection, empty/error states, responsive.
- [x] SARIF 2.1.0 export (GitHub Code Scanning inline alerts) — delivered.
- [ ] GitHub / GitLab action (audit on PR with inline comments).
- [ ] Comparison between audits (health diff over time).

## v0.5 — Governance
- [x] Multi-provider LLM factory (`init_chat_model`) configurable via env — **delivered** (Anthropic, OpenAI, Google, Groq, Mistral, DeepSeek, Ollama, Bedrock, …).
- [ ] Audit profiles (e.g., "OWASP", "LGPD", "pre-production") as presets.
- [ ] Configurable severity policies and approval gates.
- [ ] Signed audit trail (provenance of findings).

## Ideas under evaluation
- "Chat with the report" mode (questions about the findings after the audit).
- Prioritization by estimated remediation effort.
- Technical debt estimation in hours.
