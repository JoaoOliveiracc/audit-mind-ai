# Usage Guide — Audit Mind AI

## 1. Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,api]"  # dev tools + API (needed to run the full test suite)
make hooks                   # enable the security pre-commit hook
```

Requires Python ≥ 3.10.

### Global installation (run in any terminal)

By default, `auditor` only exists inside the venv. To use it from any directory:

```bash
# binary on PATH
ln -sf "$(pwd)/.venv/bin/auditor" ~/.local/bin/auditor
# global config (read from anywhere)
mkdir -p ~/.config/auditor && cp .env ~/.config/auditor/.env && chmod 600 ~/.config/auditor/.env
```

Make sure `~/.local/bin` is on your PATH (on Ubuntu it usually is; otherwise add
`export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc`).

## 2. Configuration

Copy the example and fill in your chosen provider and credential:

```bash
cp .env.example .env
```

```dotenv
AUDITOR_PROVIDER=deepseek            # anthropic | openai | google_genai | deepseek | ollama | …
DEEPSEEK_API_KEY=sk-...              # credential for the chosen provider
AUDITOR_MODEL=deepseek-chat          # model (depends on the provider)
AUDITOR_TEMPERATURE=0
AUDITOR_OUTPUT_DIR=./audit-reports
```

### Configuration precedence

The agent loads its configuration in this order (**the first source to define a
variable wins**):

1. variables already exported in the shell (e.g. `export DEEPSEEK_API_KEY=...`);
2. `.env` in the current directory (in-project development flow);
3. `~/.config/auditor/.env` (user config, used when running in any terminal).

> The global config is a **copy** of `.env` — if you change the key/provider, edit
> `~/.config/auditor/.env` (or copy `.env` again).

Available variables (all optional except the key):

| Variable | Default | Description |
| --- | --- | --- |
| `AUDITOR_PROVIDER` | `anthropic` | LLM provider (anthropic, openai, google_genai, groq, ollama, …). |
| `<PROVIDER>_API_KEY` | — | Credential for the chosen provider (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`). |
| `AUDITOR_MODEL` | `claude-sonnet-4-5` | Model used (depends on the provider). |
| `AUDITOR_BASE_URL` | — | Custom endpoint (Ollama, OpenAI-compatible gateways). |
| `AUDITOR_TEMPERATURE` | `0` | Generation temperature. |
| `AUDITOR_MAX_TOKENS` | `8000` | Max. output tokens per call. |
| `AUDITOR_MAX_FILE_BYTES` | `200000` | Max. bytes read per file. |
| `AUDITOR_MAX_FILES` | `5000` | Max. files in the inventory. |
| `AUDITOR_MAX_SEARCH_RESULTS` | `50` | Max. results per search. |
| `AUDITOR_MAX_INVESTIGATOR_STEPS` | `80` | `recursion_limit` per investigator (graph steps ≈ 2× tool calls). Near the end the agent is told to conclude; if it still runs out, a salvage report is written and the dimension is marked **partial**. |
| `AUDITOR_MAX_CONCURRENT_INVESTIGATORS` | `4` | Investigators (and adversarial-judge calls) running in parallel (1 = sequential). Lower it for Ollama/low rate limits. |
| `AUDITOR_OUTPUT_DIR` | `./audit-reports` | Output directory for the reports. |
| `AUDITOR_LOG_LEVEL` | `INFO` | Diagnostic log level (stderr). |
| `AUDITOR_ALLOWED_HOSTS` | — | Extra `Host` values the API accepts besides `localhost`/`127.0.0.1`/`[::1]` (comma-separated). Only for deliberate exposure with `serve --allow-remote`. |
| `AUDITOR_VERIFY_EVIDENCE` | `true` | Deterministic evidence check (drops unsubstantiated findings). |
| `AUDITOR_ADVERSARIAL_VERIFY` | `false` | Skeptical LLM judge (costs tokens). |
| `AUDITOR_ADVERSARIAL_MIN_SEVERITY` | `high` | Only judge findings at or above this severity. |
| `AUDITOR_ADVERSARIAL_VOTES` | `1` | Verdicts per finding (1–3 distinct lenses; majority wins). |

## 3. Running an audit

### Interactive mode (recommended)

```bash
auditor audit /path/to/project --goal "Pre-production review, security and testing focus"
```

Terminal flow:
1. The agent detects the stack and shows progress.
2. It asks clarification questions — answer them or press Enter to skip.
3. It runs the investigators per dimension (live progress).
4. It verifies each finding's evidence on disk (and, if enabled, runs the adversarial judge).
5. It consolidates, scores, and writes the reports.
6. It displays the summary and the paths of the generated files.

### Non-interactive mode (CI/automation)

```bash
auditor audit /path/to/project --no-questions
```

### Choosing the LLM provider

Install the provider package and select it via env or flag:

```bash
pip install -e ".[openai]"          # or .[google] / .[groq] / .[deepseek] / .[ollama] / .[all-providers]

auditor audit /proj --provider openai       --model gpt-4o
auditor audit /proj --provider google_genai --model gemini-2.0-flash
auditor audit /proj --provider deepseek     --model deepseek-chat
auditor audit /proj --provider ollama       --model qwen2.5-coder:14b   # local, no key

auditor providers                   # list providers, packages and credentials
```

The `--provider`/`--model` flags override `.env` for that run only.
Providers such as **Ollama** (local) and **Bedrock**/**Vertex AI** do not use
`*_API_KEY` — they depend, respectively, on the local service and on cloud
credentials (AWS/gcloud).

> **Compatibility:** the agent uses structured output and tool-calling. Prefer
> models with good *function calling* support (most recent Anthropic/OpenAI/Google
> models, and local models such as `qwen2.5-coder`).

### Output

```
audit-reports/
├── auditoria-20260701-143022-3f9a1c2e.md      # versionable, for the repository
├── auditoria-20260701-143022-3f9a1c2e.html    # self-contained, to share
└── auditoria-20260701-143022-3f9a1c2e.sarif   # SARIF 2.1.0 (GitHub Code Scanning / CI)
```

## 4. Interpreting the report

- **Health score (0–100):** heuristic based on the severities. ≥75 good,
  50–74 caution, <50 critical.
- **Severities:** `critical` > `high` > `medium` > `low` > `info`.
- **Confidence:** the agent's estimate (0–100%) about the finding. Low-confidence
  findings warrant human verification.
- **Evidence:** the actual snippet inspected by the agent — always check the file/line.

> The report is a **decision aid**, not a verdict. Review critical findings manually.

## 5. Programmatic use

```python
from auditor.graph import build_graph
from langgraph.types import Command

graph = build_graph()
config = {"configurable": {"thread_id": "my-audit"}}

state = {"project_path": "/proj", "user_goal": "", "user_context": {},
         "provider": "anthropic", "model": "claude-sonnet-4-5",  # optional per-run override
         "findings": [], "dimension_summaries": []}

# run until the clarification interrupt
result = graph.invoke(state, config)
if "__interrupt__" in result:
    questions = result["__interrupt__"][0].value["questions"]
    answers = {q["question"]: "production" for q in questions}
    result = graph.invoke(Command(resume=answers), config)

final = graph.get_state(config).values
print(final["health_score"], final["report_html_path"])
```

## 6. Troubleshooting

| Symptom | Likely cause | Solution |
| --- | --- | --- |
| `auditor: command not found` | venv not activated / no global installation | Activate the venv or perform the global installation (§1). |
| `... requires the environment variable '<PROVIDER>_API_KEY'` | missing provider credential | Set the key in `.env` (or `~/.config/auditor/.env`). |
| `RESOURCE_EXHAUSTED` / `credit balance too low` | provider quota/billing | Switch providers (`--provider`) or add credits. |
| Dimension summary starts with `⚠️ Investigação parcial` (timeline: *parcial — orçamento esgotado*) | the investigator ran out of steps; its report was salvaged from what it had inspected | Increase `AUDITOR_MAX_INVESTIGATOR_STEPS` or narrow the focus with `--goal`. |
| API answers `400 Host não permitido.` | request `Host` is not loopback (e.g. a custom hostname or LAN IP) | Use `localhost`/`127.0.0.1`, or add the host to `AUDITOR_ALLOWED_HOSTS`. |
| Audit shows `interrompida` in the history | the API process stopped while it ran (restart, `--reload`) | Click **Retomar** (`POST /audits/{id}/resume`); the interrupted step re-runs. |
| `~/.config/auditor/audits-checkpoints.sqlite` is very large | legacy audits (before the G29 fix) stored every sub-agent step | Stop the API and run `auditor db compact`; delete unwanted audits from the web history (`DELETE /audits/{id}`). |
| Slow/expensive audit | too many dimensions/files | Reduce `AUDITOR_MAX_FILES` or use `--goal` to narrow the focus. |
| Few findings | insufficient context | Answer the clarification questions in detail. |

## 7. Usage best practices

- Run the audit on a clean copy of the repository (without build artifacts).
- Use `--goal` to steer the focus (e.g. "only security and dependencies").
- Version the `.md` in the repository to track its evolution over time.
- Treat the score as a trend, not as an absolute grade.
