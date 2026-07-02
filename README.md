# Auditor-IA 🕵️

Agent de **auditoria de projetos de desenvolvimento**, agnóstico de stack, construído com **LangGraph + LangChain** e **multi-provider de LLM** (Anthropic, OpenAI, Google, Groq, Mistral, DeepSeek, Ollama local, Bedrock…).

O agent descobre a stack do projeto, conversa com você para esclarecer o escopo, executa investigadores especializados por dimensão (segurança, qualidade, arquitetura, testes, dependências, etc.) e emite um **relatório completo em Markdown e HTML**.

---

## ✨ Características

- **Agnóstico de stack** — detecta automaticamente linguagens, frameworks e gerenciadores de pacote (Python, Node, Go, Rust, Java, PHP, Ruby, .NET, e mais).
- **Multi-provider de LLM** — troca de provedor por variável de ambiente ou flag de CLI (`--provider`), via `init_chat_model`. Suporta Anthropic, OpenAI, Google, Groq, Mistral, DeepSeek, Ollama (local), Bedrock, entre outros.
- **Human-in-the-loop** — o agent faz perguntas de esclarecimento antes de auditar, usando `interrupt` do LangGraph.
- **Investigadores ReAct por dimensão** — cada dimensão é auditada por um sub-agent que explora o código com ferramentas (ler arquivo, listar diretório, buscar padrões).
- **Saída estruturada** — achados validados por Pydantic (severidade, evidência, recomendação, confiança).
- **Relatório profissional** — Markdown versionável + HTML auto-contido e estilizado, com pontuação de saúde 0–100.
- **Seguro por design** — ferramentas são **read-only** e escopadas à raiz do projeto (proteção contra path traversal). O agent audita, nunca altera.

## 🏗️ Arquitetura em uma imagem

```
START → discovery → plan_questions → clarify ─(interrupt)→ planning
      → audit(⇉ investigadores ReAct por dimensão) → synthesis → report → END
```

Detalhes em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) e [`docs/AGENT_DESIGN.md`](docs/AGENT_DESIGN.md).

## 🚀 Início rápido

```bash
# 1. Ambiente
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make hooks          # ativa o hook de pre-commit de segurança (bloqueia segredos)

# 2. Credenciais
cp .env.example .env
# edite .env: defina AUDITOR_PROVIDER e a chave do provedor (ex.: DEEPSEEK_API_KEY, ANTHROPIC_API_KEY)

# 3. Auditar um projeto
auditor audit /caminho/do/projeto --goal "Preparando para produção, foco em segurança"
```

O agent fará algumas perguntas no terminal, executará a auditoria e gravará os
relatórios em `./audit-reports/` (configurável via `AUDITOR_OUTPUT_DIR`).

### Modo não interativo (CI/pipeline)

```bash
auditor audit /caminho/do/projeto --no-questions
```

### Rodar em qualquer terminal (instalação global)

Para usar `auditor` fora do venv, a partir de qualquer diretório:

```bash
# 1. Symlink do binário para um diretório do PATH (~/.local/bin)
ln -sf "$(pwd)/.venv/bin/auditor" ~/.local/bin/auditor

# 2. Config global, lida de qualquer lugar
mkdir -p ~/.config/auditor && cp .env ~/.config/auditor/.env && chmod 600 ~/.config/auditor/.env
```

A configuração é carregada nesta ordem (**a primeira fonte vence**):
1. variáveis já exportadas no shell;
2. `.env` do diretório atual (fluxo de desenvolvimento);
3. `~/.config/auditor/.env` (config de usuário, para uso global).

> A config global é uma **cópia** do `.env` — ao trocar chave/provedor, atualize `~/.config/auditor/.env`.

## 🔌 Provedores de LLM

O provedor é configurável via `AUDITOR_PROVIDER` (no `.env`) ou pela flag `--provider`.
Cada provedor exige seu pacote de integração e sua credencial:

```bash
# instale o(s) provedor(es) desejado(s)
pip install -e ".[openai]"        # ou .[google], .[groq], .[deepseek], .[ollama], .[all-providers]

# use por flag (sobrescreve o .env)
auditor audit /proj --provider openai      --model gpt-4o
auditor audit /proj --provider google_genai --model gemini-2.0-flash
auditor audit /proj --provider groq        --model llama-3.3-70b-versatile
auditor audit /proj --provider deepseek    --model deepseek-chat
auditor audit /proj --provider ollama      --model qwen2.5-coder:14b   # 100% local

auditor providers   # lista todos os provedores, pacotes e credenciais
```

> **Ollama (local):** ideal para auditar código sensível sem enviar dados à nuvem.
> Defina `AUDITOR_BASE_URL=http://localhost:11434` se necessário.

## 📋 Comandos

| Comando | Descrição |
| --- | --- |
| `auditor audit PATH [--goal TXT] [--no-questions] [--provider P] [--model M]` | Executa a auditoria e emite o relatório. |
| `auditor serve [--host H] [--port N] [--reload]` | Sobe a API FastAPI (para o frontend web). |
| `auditor providers` | Lista os provedores de LLM suportados. |
| `auditor version` | Mostra a versão. |

### API web (backend)

```bash
pip install -e ".[api]"
auditor serve            # http://127.0.0.1:8000 — docs interativas em /docs
```

Endpoints: `POST /audits` (inicia), `GET /audits/{id}/stream` (SSE de progresso e
esclarecimentos), `POST /audits/{id}/answers` (human-in-the-loop), `GET /audits/{id}/findings`
(JSON), `GET /audits/{id}/report?format=html|md`. Estado persistido via `SqliteSaver`.
Design completo em [`docs/FRONTEND_SPEC.md`](docs/FRONTEND_SPEC.md).

### Interface web (frontend React/Next.js)

Frontend em `web/` (Next.js + Tailwind) com 3 telas: nova auditoria, execução ao
vivo (progresso + esclarecimentos via SSE) e dashboard do relatório (achados por
severidade, filtros, export).

```bash
# 1. Backend (terminal A)
auditor serve                       # http://127.0.0.1:8000

# 2. Frontend (terminal B)
cd web && npm install && npm run dev # http://localhost:3020
```

Ou tudo junto: `make dev` (sobe API + frontend). Configure a URL da API em
`web/.env.local` (`NEXT_PUBLIC_API_URL`, padrão `http://127.0.0.1:8000`).

> As portas padrão são **8000** (API) e **3000** (web). Se já houver serviços
> nelas, ajuste `auditor serve --port` e `NEXT_PUBLIC_API_URL`/porta do Next.

## 🧪 Testes

```bash
pytest -q          # testes de fumaça (offline, sem LLM)
```

## 📚 Documentação

- [`docs/SPEC.md`](docs/SPEC.md) — especificação funcional e requisitos.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — arquitetura, grafo e estado.
- [`docs/AGENT_DESIGN.md`](docs/AGENT_DESIGN.md) — design do agent e decisões (best practices LangChain).
- [`docs/USAGE.md`](docs/USAGE.md) — guia de uso, configuração e extensão.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — evolução planejada.
- [`docs/FRONTEND_SPEC.md`](docs/FRONTEND_SPEC.md) — spec da interface web (React/Next + FastAPI).
- [`SECURITY.md`](SECURITY.md) — política de segredos e proteções (hook de pre-commit).

## ⚙️ Configuração

Todas as opções vêm de variáveis de ambiente (ver [`.env.example`](.env.example)):
`ANTHROPIC_API_KEY`, `AUDITOR_MODEL`, `AUDITOR_TEMPERATURE`, `AUDITOR_MAX_FILES`,
`AUDITOR_MAX_INVESTIGATOR_STEPS`, `AUDITOR_OUTPUT_DIR`, entre outras.

## 📄 Licença

MIT.
