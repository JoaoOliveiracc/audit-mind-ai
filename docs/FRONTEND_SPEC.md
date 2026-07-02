# Spec de Frontend & API — Auditor-IA

Especificação de arquitetura para uma interface web (React + Next.js) sobre o
agent existente, em **modo local/desktop** (um usuário, sem servidor dedicado).

> Status: **design** (nenhum código ainda). Este documento antecede a implementação.

---

## 1. Objetivos e restrições

- **Reaproveitar o núcleo:** o grafo LangGraph (`src/auditor`) não muda; a API é
  apenas mais uma camada de entrada, ao lado do CLI.
- **Local/desktop:** backend e frontend rodam em `localhost`, um usuário. Sem
  multi-tenant, sem login. Simplicidade > escalabilidade.
- **Segurança do segredo:** a chave do provedor de LLM vive **apenas no backend**
  (`.env` / `~/.config/auditor/.env`) e **nunca** trafega para o navegador.
- **Experiência rica:** dashboard de achados (severidades, filtros), progresso ao
  vivo e chat de esclarecimentos.

### Não-objetivos (v1)
- Autenticação/usuários, multi-tenant, billing.
- Execução remota / fila distribuída.
- Empacotamento como app nativo (Electron/Tauri) — considerado no §10.

---

## 2. Arquitetura

```
┌─────────────────────────────┐        ┌───────────────────────────────┐
│  Frontend (Next.js/React)   │        │  Backend (FastAPI, localhost)  │
│                             │  HTTP  │                               │
│  • Nova auditoria (form)    │ ─────► │  POST /audits                 │
│  • Progresso ao vivo        │  SSE   │  GET  /audits/{id}/stream     │
│  • Chat de esclarecimentos  │ ◄───── │  POST /audits/{id}/answers    │
│  • Dashboard de relatório   │        │  GET  /audits/{id}/report     │
│                             │        │  GET  /providers              │
└─────────────────────────────┘        └───────────────┬───────────────┘
        localhost:3000                                  │ invoca
                                                        ▼
                                        ┌───────────────────────────────┐
                                        │  Núcleo — grafo LangGraph      │
                                        │  (discovery→clarify→audit→…)   │
                                        │  Checkpointer: SqliteSaver     │
                                        └───────────────────────────────┘
```

- **Backend:** FastAPI + Uvicorn em `127.0.0.1:8000`. Reusa `build_graph()`.
- **Frontend:** Next.js (App Router) em `127.0.0.1:3000`, consumindo a API via
  `fetch` + `EventSource` (SSE).
- **Persistência:** `SqliteSaver` (arquivo `~/.config/auditor/audits.sqlite`) para
  o estado do grafo (permite pausar no `interrupt` e retomar entre requisições e
  até após reinício do backend). Metadados de auditorias (lista/histórico) na
  mesma base.

---

## 3. Design da API (FastAPI)

### 3.1 Endpoints

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/providers` | Lista provedores suportados (reusa `PROVIDER_PACKAGE`). |
| `POST` | `/audits` | Cria e inicia uma auditoria. Retorna `{id, status}`. |
| `GET` | `/audits` | Lista auditorias (histórico local). |
| `GET` | `/audits/{id}` | Estado atual + resumo (health score, contagem por severidade). |
| `GET` | `/audits/{id}/stream` | **SSE**: eventos de progresso, esclarecimento e conclusão. |
| `POST` | `/audits/{id}/answers` | Envia respostas de esclarecimento → retoma o grafo. |
| `GET` | `/audits/{id}/findings` | Achados estruturados (JSON) para o dashboard. |
| `GET` | `/audits/{id}/report?format=html\|md` | Relatório renderizado. |
| `DELETE` | `/audits/{id}` | Remove a auditoria e artefatos. |

### 3.2 Schemas (Pydantic — reaproveitados do núcleo)

```jsonc
// POST /audits  (request)
{
  "project_path": "/home/joao/proj",
  "goal": "Revisão de segurança pré-produção",  // opcional
  "provider": "deepseek",                        // opcional (sobrescreve .env)
  "model": "deepseek-chat",                      // opcional
  "interactive": true                            // se false, pula esclarecimentos
}

// POST /audits/{id}/answers  (request)
{ "answers": { "Ambiente de produção?": "sim, produção crítica" } }
```

Os achados já existem como `Finding` (Pydantic) no núcleo — o endpoint
`/findings` serializa `state["findings"]` diretamente (nenhum renderer novo).

### 3.3 Streaming (SSE) — o ponto central

O backend roda o grafo em uma **task de background** por auditoria e publica
eventos numa fila em memória; o `GET /stream` drena a fila (com replay dos eventos
já ocorridos, para reconexão). Tipos de evento SSE:

| `event` | `data` | Quando |
| --- | --- | --- |
| `phase` | `{node, label, status}` | Início/fim de cada nó (discovery, planning, …). |
| `investigator` | `{dimension, status, findings_count}` | Progresso por dimensão na fase de auditoria. |
| `clarification` | `{questions:[{question, rationale}]}` | Grafo atingiu o `interrupt`; front abre o chat. |
| `finding` | `{dimension, title, severity, …}` | (Opcional) achado emitido em tempo real. |
| `completed` | `{health_score, counts, report_url}` | Auditoria concluída. |
| `error` | `{message}` | Falha. |

**Progresso granular por investigador:** hoje o nó `audit` processa todas as
dimensões internamente (emitiria só um evento no `stream_mode="updates"`). Para o
front receber progresso por dimensão, o nó `audit` deve emitir eventos via o
**stream writer do LangGraph** (`get_stream_writer()` / `stream_mode="custom"`).
Essa é a única alteração relevante no núcleo (pequena e opcional).

### 3.4 Fluxo human-in-the-loop (interrupt) na web

```
Frontend                         Backend                        Grafo
   │  POST /audits                  │                              │
   │ ─────────────────────────────►│  cria thread_id, task bg ───►│ discovery…
   │  GET /stream (abre SSE)        │                              │
   │ ◄──── phase(discovery) ────────│ ◄────────────────────────────│
   │ ◄──── clarification(perguntas)─│ ◄── interrupt() ─────────────│ (pausa)
   │  [usuário responde no chat]    │                              │
   │  POST /answers ───────────────►│  Command(resume=answers) ───►│ (retoma)
   │ ◄──── phase(planning/audit) ───│ ◄────────────────────────────│
   │ ◄──── completed ───────────────│ ◄────────────────────────────│ END
```

O `SqliteSaver` garante que o estado sobrevive à espera pela resposta (a task de
background aguarda um `asyncio.Event` até `/answers` chegar).

### 3.5 CORS e segurança local
- CORS restrito a `http://localhost:3000` / `127.0.0.1:3000`.
- Backend escuta **apenas** em `127.0.0.1` (não expõe na rede).
- `project_path` é lido do disco local — aceitável para ferramenta de um usuário;
  as tools continuam **read-only**. Validar que o caminho existe e é diretório.
- Chave de LLM nunca vai ao browser; `GET /providers` informa só nomes/credencial exigida, não valores.

---

## 4. Design do Frontend (Next.js)

### 4.1 Telas

1. **Nova Auditoria** — formulário: caminho do projeto, objetivo, provedor/modelo
   (dropdown de `/providers`), toggle "fazer perguntas de esclarecimento".
2. **Execução (ao vivo)** — timeline das fases + lista de investigadores por
   dimensão com status; abre um **painel de chat** quando chega `clarification`.
3. **Relatório (dashboard)** — cabeçalho com **health score** e distribuição por
   severidade; lista de achados filtrável (por dimensão/severidade), cada um
   expansível (descrição, evidência, recomendação, arquivo:linha); botões de
   export (HTML/MD/JSON); resumo executivo.
4. **Histórico** — lista de auditorias anteriores (de `GET /audits`).

### 4.2 Wireframes (ASCII)

```
┌── Nova Auditoria ─────────────────────────────┐
│ Caminho:  [/home/joao/proj............] [📁]  │
│ Objetivo: [Revisão pré-produção............]  │
│ Provedor: [deepseek ▾]  Modelo: [deepseek-chat]│
│ [x] Fazer perguntas de esclarecimento          │
│                              [ Iniciar auditoria ]
└───────────────────────────────────────────────┘

┌── Execução ───────────────────────────────────┐
│ ✓ Descoberta      ✓ Planejamento               │
│ ⏳ Auditoria                                    │
│    ✓ security   (5)   ⏳ quality   … perf …     │
│ ┌ Esclarecimentos ───────────────────────────┐ │
│ │ 1. Ambiente de produção?  [__________] [ok] │ │
│ └─────────────────────────────────────────────┘│
└───────────────────────────────────────────────┘

┌── Relatório ──────────────────────────────────┐
│  Saúde: 62/100   ● crit 1  ● alto 3  ● médio 5 │
│  Filtros: [dimensão ▾] [severidade ▾]  [export]│
│  ┌ [CRÍTICO] Segredo hardcoded  app.py:16  ▸  │ │
│  ┌ [ALTO]    XSS no relatório    renderer  ▸  │ │
└───────────────────────────────────────────────┘
```

### 4.3 Stack técnica do front
- **Next.js (App Router) + TypeScript**.
- **TanStack Query** para dados; **EventSource** (SSE) para o stream.
- **Tailwind CSS** + componentes (shadcn/ui) para o dashboard.
- Renderização de Markdown (react-markdown) para o resumo executivo.
- Sem estado global pesado; um store leve (Zustand) para a auditoria ativa.

---

## 5. Estrutura de diretórios proposta

```
auditor-IA/
├── src/auditor/            # núcleo (existente) — inalterado, exceto stream writer no audit
│   └── api/                # NOVO: FastAPI
│       ├── main.py         # app, CORS, rotas
│       ├── routes.py       # endpoints
│       ├── streaming.py    # gerência de tasks + fila SSE
│       ├── schemas.py      # request/response models
│       └── store.py        # SqliteSaver + metadados
├── web/                    # NOVO: frontend Next.js
│   ├── app/                # rotas (new, run, report, history)
│   ├── components/
│   └── lib/api.ts          # cliente da API + SSE
└── pyproject.toml          # + extra opcional [api] (fastapi, uvicorn, sse-starlette)
```

Novo extra em `pyproject.toml`:
```toml
api = ["fastapi>=0.115", "uvicorn[standard]>=0.30", "sse-starlette>=2.1"]
```

---

## 6. Experiência de execução local

Um alvo no `Makefile` sobe as duas partes:

```makefile
api:   ; . .venv/bin/activate && uvicorn auditor.api.main:app --host 127.0.0.1 --port 8000
web:   ; cd web && npm run dev
dev:   ; make -j2 api web        # backend + frontend juntos
```

Fluxo do usuário: `make dev` → abrir `http://localhost:3000`.

---

## 7. Alterações necessárias no núcleo (mínimas)

1. **Stream writer no nó `audit`** — emitir eventos por dimensão (`get_stream_writer()`),
   preservando o comportamento atual do CLI. **Única mudança de código essencial.**
2. **Checkpointer configurável** — `build_graph()` já aceita `checkpointer`; a API
   passa um `SqliteSaver`. Sem refactor.
3. **Export JSON de achados** — trivial: serializar `state["findings"]` (já são dicts).

Nada no fluxo de auditoria em si muda — o núcleo permanece agnóstico de interface.

---

## 8. Plano de implementação em fases

| Fase | Entregável | Depende de |
| --- | --- | --- |
| **F1 — API base** | `/providers`, `/audits` (start), `/audits/{id}`, `/report` (modo `--no-questions`); SqliteSaver | núcleo |
| **F2 — Streaming** | SSE de fases + stream writer por dimensão no nó `audit` | F1 |
| **F3 — Human-in-the-loop** | `clarification` via SSE + `POST /answers` (resume) | F2 |
| **F4 — Frontend MVP** | Telas Nova Auditoria + Execução + Relatório | F1–F3 |
| **F5 — Dashboard & histórico** | Filtros, export, tela de histórico | F4 |
| **F6 — Polimento** | Erros, reconexão SSE, empty states, responsivo | F5 |

MVP navegável ≈ F1→F4.

---

## 9. Riscos e decisões em aberto

- **Progresso por dimensão** exige o stream writer (senão o progresso fica "grosso",
  só por nó). Recomendado implementar em F2.
- **Auditorias longas**: definir timeout/limite de tokens por auditoria e feedback
  claro de custo (já temos limites em `config`).
- **Reconexão SSE**: manter replay dos eventos por auditoria (buffer em memória +
  estado no SQLite) para o front reconectar sem perder progresso.
- **Segurança do `project_path`**: local/single-user é aceitável ler qualquer
  caminho; se um dia virar multiusuário, isso precisa de sandbox/allowlist.

---

## 10. Evolução futura (fora do escopo v1)
- Empacotar como app desktop (Tauri/Electron) para distribuição sem terminal.
- Autenticação + histórico por usuário (caminho para o cenário "app web").
- WebSocket no lugar de SSE se surgir necessidade de comunicação bidirecional intensa.
- "Chat com o relatório" (perguntas sobre os achados após a auditoria).
```
