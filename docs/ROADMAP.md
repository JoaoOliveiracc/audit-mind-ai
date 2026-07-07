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

## v0.2 — Scale and performance
- [ ] **Parallelize investigators** via LangGraph's *Send API* (fan-out per dimension).
- [ ] **Persistent checkpointer** (`SqliteSaver`) to pause/resume audits.
- [ ] Cache file reads across dimensions.
- [ ] Intelligent summarization/selection of files in very large projects (map-reduce).

## v0.3 — Analysis depth
- [ ] Optional integration with external scanners (Semgrep, Trivy, gitleaks, pip-audit/npm-audit).
- [ ] Reconciliation: scanner findings + LLM findings, with deduplication.
- [ ] Adversarial verification of findings (a second agent tries to refute each finding).
- [ ] Git history analysis (hotspots, authors, churn).

## v0.4 — Experience and integration
- [x] API layer (FastAPI) reusing the same graph — **delivered (F1–F3)**: endpoints, SSE, SQLite checkpointer and human-in-the-loop. See [`FRONTEND_SPEC.md`](FRONTEND_SPEC.md).
- [x] Structured JSON export of findings — **delivered** (`GET /audits/{id}/findings`).
- [x] Web frontend (Vite + React) — **MVP delivered (F4)**: new audit, live execution (SSE) and findings dashboard. In `frontend/` (migrated from the original Next.js `web/`, now removed).
- [ ] Frontend F5–F6: rich history, robust SSE reconnection, empty/error states, responsive.
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
