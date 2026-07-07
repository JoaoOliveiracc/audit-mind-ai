# Audit Mind AI 🕵️

A **stack-agnostic development-project auditing agent**, built with **LangGraph + LangChain** and a **multi-provider LLM layer** (Anthropic, OpenAI, Google, Groq, Mistral, DeepSeek, local Ollama, Bedrock…).

The agent discovers the project's stack, talks to you to clarify scope, runs specialized per-dimension investigators (security, quality, architecture, testing, dependencies, etc.) and produces a **complete report in Markdown and HTML**.

---

## ✨ Features

- **Stack-agnostic** — automatically detects languages, frameworks and package managers (Python, Node, Go, Rust, Java, PHP, Ruby, .NET, and more).
- **Multi-provider LLM** — switch provider via environment variable or CLI flag (`--provider`), through `init_chat_model`. Supports Anthropic, OpenAI, Google, Groq, Mistral, DeepSeek, Ollama (local), Bedrock, and others.
- **Human-in-the-loop** — the agent asks clarifying questions before auditing, using LangGraph's `interrupt`.
- **Per-dimension ReAct investigators** — each dimension is audited by a sub-agent that explores the code with tools (read file, list directory, search patterns).
- **Anti-hallucination** — every finding's evidence is checked on disk (deterministic, no LLM); unsubstantiated findings are dropped. An optional **adversarial LLM judge** then tries to refute the remaining findings before the report.
- **Structured output** — findings validated by Pydantic (severity, evidence, recommendation, confidence).
- **Professional report** — versionable Markdown + self-contained, styled HTML, with a 0–100 health score.
- **Secure by design** — tools are **read-only** and scoped to the project root (path-traversal protection). The agent audits, never modifies.

## 🏗️ Architecture at a glance

```
START → discovery → plan_questions → clarify ─(interrupt)→ planning
      → audit(⇉ per-dimension ReAct investigators)
      → verify(deterministic evidence check) → adversarial(skeptical LLM judge, optional)
      → synthesis → report → END
```

Details in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/AGENT_DESIGN.md`](docs/AGENT_DESIGN.md).

## 🚀 Quick start

```bash
# 1. Environment
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make hooks          # enable the security pre-commit hook (blocks secrets)

# 2. Credentials
cp .env.example .env
# edit .env: set AUDITOR_PROVIDER and the provider's key (e.g. DEEPSEEK_API_KEY, ANTHROPIC_API_KEY)

# 3. Audit a project
auditor audit /path/to/project --goal "Preparing for production, security focus"
```

The agent will ask a few questions in the terminal, run the audit and write the
reports to `./audit-reports/` (configurable via `AUDITOR_OUTPUT_DIR`).

### Non-interactive mode (CI/pipeline)

```bash
auditor audit /path/to/project --no-questions
```

### Run from any terminal (global installation)

To use `auditor` outside the venv, from any directory:

```bash
# 1. Symlink the binary into a directory on your PATH (~/.local/bin)
ln -sf "$(pwd)/.venv/bin/auditor" ~/.local/bin/auditor

# 2. Global config, read from anywhere
mkdir -p ~/.config/auditor && cp .env ~/.config/auditor/.env && chmod 600 ~/.config/auditor/.env
```

Configuration is loaded in this order (**first source wins**):
1. variables already exported in the shell;
2. `.env` in the current directory (development workflow);
3. `~/.config/auditor/.env` (user config, for global use).

> The global config is a **copy** of `.env` — when you change key/provider, update `~/.config/auditor/.env`.

## 🔌 LLM providers

The provider is configurable via `AUDITOR_PROVIDER` (in `.env`) or the `--provider` flag.
Each provider requires its integration package and its credential:

```bash
# install the desired provider(s)
pip install -e ".[openai]"        # or .[google], .[groq], .[deepseek], .[ollama], .[all-providers]

# select via flag (overrides .env)
auditor audit /proj --provider openai       --model gpt-4o
auditor audit /proj --provider google_genai --model gemini-2.0-flash
auditor audit /proj --provider groq         --model llama-3.3-70b-versatile
auditor audit /proj --provider deepseek     --model deepseek-chat
auditor audit /proj --provider ollama       --model qwen2.5-coder:14b   # 100% local

auditor providers   # list all providers, packages and credentials
```

> **Ollama (local):** ideal for auditing sensitive code without sending data to the cloud.
> Set `AUDITOR_BASE_URL=http://localhost:11434` if needed.

## 📋 Commands

| Command | Description |
| --- | --- |
| `auditor audit PATH [--goal TXT] [--no-questions] [--provider P] [--model M]` | Run the audit and emit the report. |
| `auditor serve [--host H] [--port N] [--reload]` | Start the FastAPI backend (for the web frontend). |
| `auditor providers` | List supported LLM providers. |
| `auditor version` | Show the version. |

### Web API (backend)

```bash
pip install -e ".[api]"
auditor serve            # http://127.0.0.1:8020 — interactive docs at /docs
```

Endpoints: `POST /audits` (start), `GET /audits` / `GET /audits/{id}` (list/status),
`GET /audits/{id}/stream` (SSE for progress and clarifications), `POST /audits/{id}/answers`
(human-in-the-loop), `GET /audits/{id}/findings` (JSON), `GET /audits/{id}/report?format=html|md`,
`GET /fs/browse` (folder picker), `GET /providers`. State persisted via `SqliteSaver`.
Full design in [`docs/FRONTEND_SPEC.md`](docs/FRONTEND_SPEC.md).

### Web interface (Vite + React frontend)

The active frontend lives in `frontend/` (Vite + React + Tailwind, with Vitest tests).
Screens: new audit (with folder picker), live run (progress + clarifications +
verification over SSE) and the report dashboard (findings by severity, filters, export).

```bash
# 1. Backend (terminal A) — default port 8020, which the Vite proxy targets
auditor serve                             # http://127.0.0.1:8020

# 2. Frontend (terminal B)
cd frontend && npm install && npm run dev # http://localhost:5173
```

Or all at once: `make dev` (starts API + Vite frontend). The Vite dev server proxies
`/audits`, `/providers`, `/health` and `/fs` to the backend on **:8020** (same origin — no
CORS setup needed; see `frontend/vite.config.ts`). Production build: `vite build` → `frontend/dist/`.

## 🧪 Tests

```bash
pytest -q          # smoke tests (offline, no LLM)
```

## 📚 Documentation

- [`DOCUMENTACAO.md`](DOCUMENTACAO.md) — technical documentation (pt-BR): architecture, code reference, gaps and roadmap.
- [`docs/SPEC.md`](docs/SPEC.md) — functional specification and requirements.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture, graph and state.
- [`docs/AGENT_DESIGN.md`](docs/AGENT_DESIGN.md) — agent design and decisions (LangChain best practices).
- [`docs/USAGE.md`](docs/USAGE.md) — usage, configuration and extension guide.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — planned evolution.
- [`docs/FRONTEND_SPEC.md`](docs/FRONTEND_SPEC.md) — web interface spec (React/Next + FastAPI).
- [`SECURITY.md`](SECURITY.md) — secrets policy and protections (pre-commit hook).

## ⚙️ Configuration

All options come from environment variables (see [`.env.example`](.env.example)):
`ANTHROPIC_API_KEY`, `AUDITOR_MODEL`, `AUDITOR_TEMPERATURE`, `AUDITOR_MAX_FILES`,
`AUDITOR_MAX_INVESTIGATOR_STEPS`, `AUDITOR_OUTPUT_DIR`, among others.

## 📄 License

MIT.
