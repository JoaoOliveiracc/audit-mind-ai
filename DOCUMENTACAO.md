# Audit Mind AI — Documentação Técnica

> Agente de auditoria de projetos de desenvolvimento, **agnóstico de stack**, construído com
> **LangGraph + LangChain** e uma **camada multi-provider de LLM** (Anthropic, OpenAI, Google,
> Groq, Mistral, DeepSeek, Ollama local, Bedrock…).
>
> O agente descobre a stack do projeto, conversa com o usuário para focar o escopo, roda
> **investigadores ReAct** especializados por dimensão (segurança, qualidade, arquitetura,
> testes, dependências, etc.), **verifica a evidência** de cada achado no disco (anti-alucinação),
> opcionalmente submete os achados a um **juiz adversarial** e produz um relatório completo em
> **Markdown + HTML** com uma pontuação de saúde de 0–100.

> ℹ️ **Este documento foi reescrito** para refletir a arquitetura atual (`src/auditor/`, LangGraph).
> A versão anterior descrevia o protótipo single-file `app.py`, hoje **removido** (inclusive do
> histórico do git) — ver [§12 Legado](#12-legado-appy-removido). A maioria dos gaps originais
> (G1–G13) e das correções subsequentes (G14–G21, G23–G24) foi **resolvida**; resta a rotação
> da chave (G14) e itens de robustez (G20, G22 já resolvido) — ver [§10 Gaps](#10-gaps-identificados).

---

## Sumário

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura](#2-arquitetura)
3. [Pré-requisitos](#3-pré-requisitos)
4. [Instalação](#4-instalação)
5. [Configuração](#5-configuração)
6. [Como Usar](#6-como-usar)
7. [Referência do Código](#7-referência-do-código)
8. [Fluxo de Execução](#8-fluxo-de-execução)
9. [Anti-alucinação: verificação de evidência e juiz adversarial](#9-anti-alucinação-verificação-de-evidência-e-juiz-adversarial)
10. [Gaps Identificados](#10-gaps-identificados)
11. [Melhorias Sugeridas (Roadmap)](#11-melhorias-sugeridas-roadmap)
12. [Legado: `app.py` (removido)](#12-legado-appy-removido)

---

## 1. Visão Geral

| Item | Valor |
|------|-------|
| Linguagem | Python ≥ 3.10 |
| Orquestração | **LangGraph** (grafo com estado + checkpointer) |
| Framework LLM | LangChain (`init_chat_model` — multi-provider) |
| Provider padrão | `anthropic` / `claude-sonnet-4-5` (configurável) |
| Providers suportados | anthropic, openai, azure_openai, google_genai, google_vertexai, groq, mistralai, cohere, together, fireworks, deepseek, bedrock, ollama |
| Interfaces | CLI (`auditor`), API REST (FastAPI + SSE), Frontend web (Vite/React) |
| Estado | Persistido em SQLite (`SqliteSaver` + metadados) sob `~/.config/auditor/` |
| Saída | Relatório Markdown + HTML autocontido + **SARIF 2.1.0**; findings em JSON via API |
| Pacote | `src/auditor/` (~2.5k linhas), instalável (`pip install -e .`), entry point `auditor` |

**Objetivo:** dado o caminho de um projeto, detectar sua stack, planejar as dimensões de
auditoria relevantes, investigar cada dimensão com um sub-agente munido de ferramentas
**read-only** e escopadas à raiz do projeto, filtrar achados não-substanciados e emitir um
relatório profissional — sem nunca modificar o código auditado.

---

## 2. Arquitetura

```
┌───────────────────────── Interfaces ─────────────────────────┐
│  CLI (Typer/Rich)   ·   API REST (FastAPI + SSE)   ·   Web UI  │
│    auditor audit          auditor serve               (Vite)  │
└───────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌───────────────────── Grafo LangGraph (StateGraph) ─────────────────────┐
│                                                                         │
│  START → discovery → plan_questions → clarify ─(interrupt)→ planning    │
│        → audit (⇉ investigadores ReAct por dimensão)                    │
│        → verify (checagem determinística de evidência)                  │
│        → adversarial (juiz LLM cético, opcional)                        │
│        → synthesis (pontuação + resumo) → report → END                  │
│                                                                         │
│  Estado: AuditState (TypedDict) · Checkpointer: MemorySaver (CLI) /     │
│          SqliteSaver (API)                                              │
└──────────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
        LLM (init_chat_model)  ──►  provider configurado (nuvem ou Ollama local)
        Tools read-only        ──►  filesystem escopado à raiz do projeto
```

**Camadas / pacotes:**

- `auditor.graph` — monta e compila o `StateGraph` (9 nós, arestas lineares).
- `auditor.state` — `AuditState` (estado do grafo) + modelos Pydantic de domínio
  (`Finding`, `DimensionResult`, `Verdict`, `StackProfile`, `AuditPlan`, `ClarifyingQuestions`).
- `auditor.nodes.*` — um módulo por nó do grafo.
- `auditor.tools.*` — ferramentas read-only (`filesystem`) e utilitários de descoberta (`project`).
- `auditor.prompts.templates` — prompts de sistema, guidance por dimensão, lentes do juiz.
- `auditor.report.renderer` / `auditor.report.sarif` — renderização Markdown/HTML (Jinja2) e SARIF 2.1.0.
- `auditor.llm` / `auditor.config` — fábrica de LLM multi-provider e configurações (`pydantic-settings`).
- `auditor.cli` — CLI Typer (`audit`, `serve`, `providers`, `version`).
- `auditor.api.*` — FastAPI: rotas, runner em background, store SQLite, schemas.

**Componentes LangGraph/LangChain usados:**

- `StateGraph` / `create_react_agent` — grafo de auditoria + investigadores ReAct por dimensão.
- `interrupt` + checkpointer — human-in-the-loop no nó `clarify`.
- `init_chat_model` — abstração multi-provider (troca de provider por env/flag).
- `with_structured_output(...)` — saída Pydantic validada (planos, achados, vereditos).
- `SqliteSaver` — persistência de estado do grafo entre processos (modo API).

---

## 3. Pré-requisitos

- Python ≥ 3.10 (recomendado 3.12).
- Credencial do provider escolhido (ex.: `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`) — **exceto**
  Ollama (local), Bedrock (credenciais AWS) e Vertex AI (gcloud), que não usam chave própria.
- Para auditar código sensível sem enviá-lo à nuvem: **Ollama local** + `AUDITOR_BASE_URL=http://localhost:11434`.
- Para a API/web: extras `.[api]` (FastAPI, uvicorn, sse-starlette, checkpointer SQLite) e Node.js
  (frontend Vite).

Dependências versionadas em `pyproject.toml` (núcleo) e em `requirements.txt`. Providers e a
camada de API são **extras opcionais** (`.[openai]`, `.[ollama]`, `.[api]`, `.[all-providers]`…).

---

## 4. Instalação

```bash
# 1. Ambiente + dependências de dev + hook de segurança
make install            # cria .venv, instala .[dev] e ativa o pre-commit hook
# (equivalente manual:)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make hooks              # git config core.hooksPath .githooks (bloqueia commit de segredos)

# 2. Credenciais
cp .env.example .env
# edite .env: AUDITOR_PROVIDER + a chave do provider (ex.: ANTHROPIC_API_KEY)

# 3. Provider(s) adicionais, se necessário
pip install -e ".[openai]"        # ou .[google], .[groq], .[deepseek], .[ollama], .[all-providers]

# 4. API/web (opcional)
pip install -e ".[api]"
```

**Uso global (rodar `auditor` de qualquer diretório):**

```bash
ln -sf "$(pwd)/.venv/bin/auditor" ~/.local/bin/auditor
mkdir -p ~/.config/auditor && cp .env ~/.config/auditor/.env && chmod 600 ~/.config/auditor/.env
```

Precedência de configuração (**a primeira fonte vence**): variáveis já exportadas no shell →
`.env` do diretório atual → `~/.config/auditor/.env`.

---

## 5. Configuração

Toda a configuração vem de variáveis de ambiente (prefixo `AUDITOR_`), carregadas por
`pydantic-settings` em `auditor.config.Settings`. Template completo em `.env.example`.

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `AUDITOR_PROVIDER` | `anthropic` | Provider de LLM. |
| `AUDITOR_MODEL` | `claude-sonnet-4-5` | Modelo. |
| `AUDITOR_TEMPERATURE` | `0.0` | Determinístico (recomendado p/ auditoria). |
| `AUDITOR_MAX_TOKENS` | `8000` | Máx. tokens de saída por chamada. |
| `AUDITOR_BASE_URL` | `""` | Endpoint custom (Ollama, gateway OpenAI-compatible). |
| `AUDITOR_MAX_FILE_BYTES` | `200000` | Tamanho máx. por arquivo lido. |
| `AUDITOR_MAX_FILES` | `5000` | Máx. de arquivos no inventário. |
| `AUDITOR_MAX_SEARCH_RESULTS` | `50` | Máx. de resultados por busca. |
| `AUDITOR_MAX_INVESTIGATOR_STEPS` | `80` | `recursion_limit` de cada investigador ReAct. |
| `AUDITOR_MAX_CONCURRENT_INVESTIGATORS` | `4` | Investigadores de dimensão em paralelo (1 = sequencial). |
| `AUDITOR_OUTPUT_DIR` | `./audit-reports` | Diretório dos relatórios. |
| `AUDITOR_VERIFY_EVIDENCE` | `true` | Verificação determinística de evidência (§9). |
| `AUDITOR_ADVERSARIAL_VERIFY` | `false` | Juiz adversarial (custa tokens; §9). |
| `AUDITOR_ADVERSARIAL_MIN_SEVERITY` | `high` | Só julga achados ≥ este limiar. |
| `AUDITOR_ADVERSARIAL_VOTES` | `1` | Nº de vereditos por achado (1–3, lentes distintas). |

A credencial de cada provider é lida **diretamente do ambiente pela SDK correspondente**
(`ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, …); `auditor.config.PROVIDER_ENV_VAR` mapeia
provider → variável exigida, e `auditor.llm._validate_credentials` falha cedo com mensagem
acionável se ela estiver ausente. **Nenhuma chave é hardcoded no código.** O antigo protótipo
`app.py`, que continha uma, foi **removido** (ver [§12](#12-legado-appy-removido)); resta apenas
saná-la no histórico do git (ver [§10 G14](#10-gaps-identificados)).

---

## 6. Como Usar

### CLI

```bash
# Auditoria completa (faz perguntas de esclarecimento no terminal)
auditor audit /caminho/do/projeto --goal "Preparando para produção, foco em segurança"

# Não-interativo (CI/pipeline): pula os esclarecimentos
auditor audit /caminho/do/projeto --no-questions

# Trocar provider/modelo em runtime (sobrescreve o .env)
auditor audit /proj --provider ollama --model qwen2.5-coder:14b   # 100% local

auditor providers    # lista providers, pacotes e credenciais
auditor version
```

Os relatórios são gravados em `./audit-reports/` (`AUDITOR_OUTPUT_DIR`) como
`auditoria-<timestamp>.md` e `.html`.

### API REST (backend)

```bash
pip install -e ".[api]"
auditor serve                    # http://127.0.0.1:8020 — docs em /docs
```

Principais endpoints:

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET`  | `/health` | Healthcheck. |
| `GET`  | `/providers` | Providers suportados. |
| `GET`  | `/fs/browse?path=` | Lista subpastas do host (folder picker). |
| `POST` | `/audits` | Cria e inicia uma auditoria em background. |
| `GET`  | `/audits` | Lista o histórico local de auditorias. |
| `GET`  | `/audits/{id}` | Estado atual de uma auditoria. |
| `GET`  | `/audits/{id}/stream` | **SSE**: progresso, esclarecimentos e conclusão. |
| `POST` | `/audits/{id}/answers` | Envia respostas de esclarecimento (human-in-the-loop). |
| `GET`  | `/audits/{id}/findings` | Achados estruturados (JSON) para o dashboard. |
| `GET`  | `/audits/{id}/report?format=html\|md\|sarif` | Relatório renderizado (SARIF via `application/sarif+json`). |

Estado do grafo persistido em `SqliteSaver`; metadados das auditorias em SQLite
(`~/.config/auditor/audits.sqlite` e `audits-checkpoints.sqlite`). CORS restrito ao frontend local.

### Frontend web (Vite/React — `frontend/`)

Frontend **ativo** em `frontend/` (Vite + React + Tailwind, com testes Vitest). Telas: nova
auditoria (com folder picker), execução ao vivo (progresso + esclarecimentos + verificação
por SSE) e dashboard do relatório (achados por severidade, filtros, export).

```bash
# Terminal A — backend (porta padrão 8020, para onde o proxy do Vite aponta)
auditor serve                               # http://127.0.0.1:8020

# Terminal B — frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
```

> Ou tudo de uma vez: `make dev` (sobe API + frontend Vite). O dev server do Vite faz **proxy**
> de `/audits`, `/providers`, `/health` e `/fs` para o backend em **:8020** (mesma origem, sem
> problema de CORS — ver `frontend/vite.config.ts`). Em produção, `vite build` gera `dist/`.
> A porta foi **unificada em 8020** em código, Makefile, proxy do Vite e docs.

### Testes

```bash
pytest -q          # offline, sem LLM (smoke, verify, adversarial, api)
make test          # idem, dentro da .venv
make lint          # ruff check src tests
```

---

## 7. Referência do Código

### Nós do grafo (`auditor/nodes/`)

| Nó | Arquivo | Responsabilidade |
|----|---------|------------------|
| `discovery_node` | `discovery.py` | Detecta stack (`detect_stack`) e monta inventário textual (`build_inventory`). |
| `plan_questions_node` | `clarify.py` | Gera perguntas de esclarecimento (Pydantic `ClarifyingQuestions`). |
| `clarify_node` | `clarify.py` | `interrupt` para human-in-the-loop; coleta `user_context`. Pulado se `skip_questions`. |
| `planning_node` | `planning.py` | LLM seleciona as dimensões aplicáveis (`AuditPlan`); fallback p/ dimensões padrão. |
| `audit_node` | `audit.py` | Um `create_react_agent` por dimensão (com tools read-only), rodando **em paralelo** (thread pool, `AUDITOR_MAX_CONCURRENT_INVESTIGATORS`); agrega `Finding`s na ordem do plano. Emite eventos SSE pela thread principal. |
| `verify_node` | `verify.py` | Verificação **determinística** de evidência no disco (sem LLM); descarta achados alucinados. |
| `adversarial_node` | `adversarial.py` | Juiz LLM cético (opcional) refuta achados elegíveis; votação por lentes. |
| `synthesis_node` | `synthesis.py` | `compute_health_score` (0–100) + resumo executivo + contagem por severidade. |
| `report_node` | `report.py` | Renderiza e grava Markdown + HTML + SARIF (`report/sarif.py`). |

### Ferramentas read-only (`auditor/tools/filesystem.py`)

Vinculadas à raiz do projeto via `make_project_tools(root, settings)`; todo caminho passa por
`_safe_resolve` (proteção contra **path traversal** — fora da raiz é rejeitado):

- `read_file(path, start_line, max_lines)` — lê arquivo de texto (numera linhas, respeita limites, ignora binários).
- `list_directory(path)` — lista diretório do projeto.
- `search_code(pattern, glob, is_regex)` — busca por conteúdo (literal ou regex) com glob.

### Descoberta (`auditor/tools/project.py`)

- `detect_stack(root, settings) -> StackProfile` — linguagens, frameworks, gerenciadores de pacote, flags (`has_tests`/`has_ci`/`has_docker`/`has_git`), LOC.
- `build_inventory(root, settings)` — árvore resumida + metadados textuais.

### Estado e modelos (`auditor/state.py`)

- `AuditState(TypedDict)` — estado compartilhado; `dimension_summaries` acumula via `operator.add`, `messages` via `add_messages`. `findings` é **reescrito** por `verify`/`adversarial` (lista filtrada).
- `Finding` — `dimension, title, severity, description, recommendation, file, line, evidence, confidence, verified, judged`.
- `Severity` + `SEVERITY_WEIGHT` — pesos usados na pontuação de saúde (critical=40, high=20, medium=8, low=3, info=0).

### Pontuação de saúde (`auditor/nodes/synthesis.py`)

```python
penalty = Σ SEVERITY_WEIGHT[severity]  (por achado)
health_score = max(0, 100 - min(100, penalty))
```

### LLM e config

- `auditor.llm.get_llm()` — memoiza o chat model via `init_chat_model`; `reset_llm_cache()` no override runtime.
- `auditor.config.get_settings()` — singleton `Settings` (`lru_cache`).

### API (`auditor/api/`)

- `main.py` — app FastAPI + CORS + `/health`.
- `routes.py` — endpoints (ver §6).
- `runner.py` — executa o grafo em background por thread, acumulando eventos p/ o SSE.
- `store.py` — `SqliteSaver` (checkpointer) + `AuditStore` (metadados) em `~/.config/auditor/`.
- `deps.py` — singletons (`get_graph`, `get_store`, `registry`).

---

## 8. Fluxo de Execução

1. **discovery** — varre o projeto, detecta a stack, monta o inventário.
2. **plan_questions** — gera perguntas de esclarecimento com base na descoberta.
3. **clarify** — `interrupt`: pausa e aguarda respostas do usuário (CLI ou API). Pulado com `--no-questions`.
4. **planning** — o LLM escolhe as dimensões relevantes e as notas de foco.
5. **audit** — para cada dimensão, um investigador ReAct explora o código com as tools read-only
   e retorna um `DimensionResult` estruturado; os investigadores rodam **em paralelo** (thread
   pool) e os achados são agregados na ordem do plano.
6. **verify** — cada achado é conferido no disco (arquivo existe? evidência aparece? linha no
   intervalo?). Não-substanciados são **descartados**; sem-evidência têm confiança rebaixada.
7. **adversarial** *(opcional)* — juiz LLM cético tenta refutar cada achado elegível; refutados
   são descartados, incertos rebaixados.
8. **synthesis** — pontuação de saúde (0–100), contagem por severidade, resumo executivo.
9. **report** — grava `auditoria-<timestamp>.md` e `.html`.

O checkpointer permite pausar em `clarify` e retomar (`Command(resume=answers)`), inclusive
entre processos no modo API (SQLite).

---

## 9. Anti-alucinação: verificação de evidência e juiz adversarial

Diferencial central do agente frente a "colar o repo num prompt": **os achados são checados
antes de entrar no relatório.**

### `verify_node` — determinístico, sem LLM (`AUDITOR_VERIFY_EVIDENCE=true`)

Para cada achado com `file`/`evidence`, confere no disco:
- o arquivo citado **existe** e está dentro da raiz (senão → `rejected`);
- o trecho de `evidence` realmente **aparece** no arquivo (heurística tolerante: match direto,
  sobreposição linha-a-linha ≥ 50%, ou maior trecho comum via `difflib`);
- a `line` está no intervalo do arquivo.

Achados `rejected` são removidos (possível alucinação); `unverified` (sem arquivo/evidência
para conferir, ex.: achados arquiteturais) são mantidos com `confidence ≤ 0.5`. **Custo zero de tokens.**

### `adversarial_node` — juiz LLM cético (`AUDITOR_ADVERSARIAL_VERIFY=true`)

Roda após o `verify` (só vê achados já substanciados). Para cada achado **elegível** (com arquivo
e severidade ≥ `AUDITOR_ADVERSARIAL_MIN_SEVERITY`), extrai a janela real de código ao redor da
linha e pede ao LLM que tente **refutar** o mérito do problema — sob até 3 lentes distintas
(`AUDITOR_ADVERSARIAL_VOTES`, decisão por maioria). Refutados são descartados como falso-positivo;
incertos são mantidos com confiança rebaixada. Custa tokens — desativado por padrão.

As estatísticas de ambos (`verified/unverified/rejected`, `confirmed/refuted/uncertain`) aparecem
no resumo da CLI, na API (`/findings`) e nos eventos SSE.

---

## 10. Gaps Identificados

### Situação dos gaps originais (protótipo `app.py`)

A grande maioria foi **resolvida** pela reescrita em `src/auditor/`:

| # | Gap original | Status |
|---|--------------|--------|
| G1 | API key hardcoded | ⚠️ **Resolvido no pacote**, mas **ainda presente no legado `app.py`** (ver abaixo). |
| G2 | `load_dotenv()` sem ler env | ✅ Resolvido — `pydantic-settings` + precedência de fontes. |
| G3 | Protocolo errado (`ChatOllama` × `/v1`) | ✅ Resolvido — `init_chat_model` multi-provider; Ollama é um provider entre vários. |
| G4 | Sem `requirements`/`pyproject` | ✅ Resolvido — `pyproject.toml` + `requirements.txt` versionados. |
| G5 | Sem `.gitignore` | ✅ Resolvido — `.gitignore` cobre `.env`, `.venv/`, `audit-reports/`. |
| G6 | Contexto inteiro reenviado a cada turno | ✅ Resolvido — investigadores ReAct leem só o necessário via tools. |
| G7 | `session_id` fixo | ✅ Resolvido — `thread_id`/`audit_id` únicos por auditoria. |
| G8 | Sem limite de tamanho | ✅ Resolvido — `max_file_bytes`, `max_files`, `max_search_results`, `max_investigator_steps`. |
| G9 | Sem saída estruturada | ✅ Resolvido — Pydantic (`Finding`, `DimensionResult`) + export JSON via API. |
| G10 | Sem streaming | ✅ Resolvido — `graph.stream` (CLI) + SSE (API). |
| G11 | Sem testes/logging | ⚙️ Parcial — há testes (`tests/`) e Rich console; logging estruturado ainda incipiente. |
| G12 | Relatório não persistido | ✅ Resolvido — Markdown + HTML em `AUDITOR_OUTPUT_DIR`. |
| G13 | Sem README/docs | ✅ Resolvido — `README.md` + `docs/*` + este documento. |

### Gaps atuais

Estado após a rodada de correções (ver [§11](#11-melhorias-sugeridas-roadmap)):

| # | Gap | Severidade | Status |
|---|-----|-----------|--------|
| **G14** | **Segredo real committado**: o legado `app.py:16` continha uma API key hardcoded. | 🔴 Crítico | ✅ **Histórico limpo** — `app.py` removido de **todos** os commits com `git filter-repo` e **force-push** em `main`/`develop`/`feature/adversarialNode`. ⚠️ **Falta ação do usuário:** (1) **ROTACIONAR** a chave no console do provider — ela esteve pública; (2) opcionalmente pedir ao GitHub Support para purgar caches/SHAs órfãos. |
| G15 | `app.py` legado no repo, fora da arquitetura atual. | 🟠 Alto | ✅ **Resolvido** — arquivo removido (`git rm app.py`). |
| G16 | Dois frontends (`frontend/` Vite × `web/` Next legado). | 🟠 Alto | ✅ **Resolvido** — `web/` removido; `frontend/` (Vite) é o oficial. |
| G17 | Porta da API inconsistente (8020/8010/8000). | 🟠 Alto | ✅ **Resolvido** — unificada em **8020** (código, `vite.config.ts`, `Makefile`, README, docs). |
| G18 | `Makefile`/README apontavam para o `web/` legado. | 🟡 Médio | ✅ **Resolvido** — alvos `frontend`/`frontend-install`/`dev` apontam para `frontend/`. |
| G19 | CORS só liberava `:3020` (Next legado). | 🟡 Médio | ✅ **Resolvido** — CORS agora libera `:5173` (Vite dev); em dev o proxy já torna same-origin. |
| G20 | Registry da API em memória por processo. | 🟡 Médio | ℹ️ **Aceito p/ uso local** — dentro do processo há replay do SSE por índice (reconexão OK); só o modo multi-instância exigiria persistir eventos. Reavaliar se houver deploy horizontal. |
| G21 | Logging estruturado ausente (só `rich.Console`). | 🟡 Médio | ✅ **Resolvido** — `auditor.logging_config` (nível via `AUDITOR_LOG_LEVEL`), aplicado na CLI, API, `llm` e runner. |
| G22 | Override de provider/modelo via `os.environ` é processo-global. | 🟢 Baixo | ⏳ **Pendente** — aceitável para a CLI (1 processo/auditoria); para a API multi-tenant exigiria isolar o LLM por run (refactor). |
| G23 | Docs secundárias (`docs/FRONTEND_SPEC.md`, `docs/ROADMAP.md`) ainda citam o `web/` Next. | 🟢 Baixo | ✅ **Resolvido** — `ROADMAP` atualizado p/ Vite; `FRONTEND_SPEC` recebeu banner de "superseded" apontando p/ `frontend/`. |
| G24 | Hook `.githooks/pre-commit`: o padrão de chave privada começava com `-`, quebrando o `grep` (detecção silenciosamente pulada). | 🟡 Médio | ✅ **Resolvido** — `grep -Eq -e "$pat"`; a varredura de chave privada volta a funcionar. |

---

## 11. Melhorias Sugeridas (Roadmap)

### Higiene imediata — ✅ feito nesta rodada (G14–G19, G21, G23–G24)
1. ✅ **`app.py` legado removido** (G15) **e apagado de todo o histórico** (`git filter-repo` +
   force-push nas 3 branches — G14). ⚠️ **Falta ação do usuário:** **rotacionar** a chave (esteve
   pública). Hook de pre-commit corrigido para detectar chaves privadas (G24).
2. ✅ **Porta da API unificada em 8020** (código, `vite.config.ts`, `Makefile`, README, docs — G17).
3. ✅ **Frontend consolidado**: `web/` (Next) removido; `frontend/` (Vite) é o oficial; `Makefile`
   atualizado (`make frontend`/`make dev`) — G16/G18.
4. ✅ **CORS** ajustado para a origem do Vite dev (`:5173`); em dev o proxy já torna same-origin — G19.
5. ✅ **Logging estruturado** (`auditor.logging_config`, nível por `AUDITOR_LOG_LEVEL`) na CLI, API,
   `llm` e runner — G21.

6. ✅ **G22 resolvido**: `get_llm(provider, model)` por auditoria, sem mutar `os.environ` global —
   auditorias concorrentes com provedores distintos deixam de colidir.

### Robustez — pendente (G20)
7. Se houver deploy multi-instância: persistir o log de eventos (ou reconstruir o SSE a partir do
   checkpointer) para o stream escalar além de um processo — G20 (aceitável no modo local atual).

### Produto / escala
8. ✅ **Export SARIF** dos findings — implementado (`auditor.report.sarif`); gravado junto ao
   MD/HTML e exposto na API (`?format=sarif`). Integra com GitHub Code Scanning / CI.
9. ✅ **Investigadores paralelos** — implementado no `audit_node` (thread pool, limite por
   `AUDITOR_MAX_CONCURRENT_INVESTIGATORS`); agregação determinística na ordem do plano.
10. RAG/indexação para monorepos gigantes (recuperar trechos por dimensão) e cache de prompt.
11. Ampliar a suíte de testes (cobertura dos nós `discovery`/`planning`/`synthesis` e um e2e com LLM mockado).

---

## 12. Legado: `app.py` (removido)

`app.py` era o **protótipo original** (single-file, ~137 linhas): um chat CLI que concatenava
todo o código do projeto num prompt de sistema e conversava com `ChatOllama`. Foi **superado**
por `src/auditor/` e **removido** do repositório nesta rodada de correções (G15).

> ✅ **Histórico já saneado:** o `app.py` foi removido de **todos** os commits com `git filter-repo`
> e as três branches (`main`/`develop`/`feature/adversarialNode`) foram force-pushed. O segredo
> não aparece mais nas pontas das branches.
>
> 🔴 **Ação ainda necessária (usuário):** a chave `sk-indexacao-…` esteve **pública** no GitHub —
> considere-a **comprometida** e:
> 1. **rotacione-a** no console do provider (imediato e imprescindível — a reescrita de histórico
>    não desfaz a exposição que já ocorreu);
> 2. opcionalmente peça ao GitHub Support para purgar caches/SHAs órfãos, pois commits antigos
>    podem seguir acessíveis por hash até o garbage collection.
>
> Ironicamente, é exatamente o tipo de achado que este agente reportaria — ver
> [§10 G14](#10-gaps-identificados).
