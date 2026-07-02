# Audit Mind AI — Security Audit Agent

> Agente de auditoria de segurança de código baseado em LangChain + LLM local (Ollama / Gemma 3).
> Lê o código-fonte de um projeto, monta um contexto único e conversa com um modelo
> instruído a atuar como **Auditor de Segurança Sênior** sob a ótica de **Zero Trust** e **OWASP**.

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
9. [Análise Crítica (Sênior LangChain)](#9-análise-crítica-sênior-langchain)
10. [Gaps Identificados](#10-gaps-identificados)
11. [Melhorias Sugeridas (Roadmap)](#11-melhorias-sugeridas-roadmap)

---

## 1. Visão Geral

| Item | Valor |
|------|-------|
| Linguagem | Python 3.12 |
| Framework | LangChain 1.x (`langchain-core==1.4.0`) |
| Provider LLM | `langchain-ollama` → `ChatOllama` |
| Modelo | `gemma3:12b` |
| Endpoint | `http://192.168.1.50/v1` (remoto) |
| Interface | CLI interativa (terminal) |
| Estado | Histórico de conversa em memória (RAM) |
| Arquivos | `app.py` (~137 linhas, single-file) |

O objetivo é: dado o caminho de um projeto, ler recursivamente os arquivos relevantes
(`.py`, `.js`, `.ts`, `.go`, `.yml`, `.yaml`, `Dockerfile`, `.env.example`), injetá-los
como contexto num prompt de sistema e obter um relatório de auditoria, seguido de um
chat de perguntas e respostas sobre os achados.

---

## 2. Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                        CLI (terminal)                          │
│   iniciar_auditoria()  →  input(caminho, nome) / loop de chat  │
└───────────────┬────────────────────────────────────────────────┘
                │
                ▼
   carregar_contexto_projeto(dir)        # os.walk + leitura de arquivos
                │  (string única gigante)
                ▼
┌──────────────────────────────────────────────────────────────┐
│            RunnableWithMessageHistory (executor)               │
│                                                                │
│   ChatPromptTemplate                                           │
│     ├─ system  (system_template + {nome_projeto}/{dados})      │
│     ├─ MessagesPlaceholder("history")                          │
│     └─ human   ({input})                                       │
│                    │                                           │
│                    ▼                                           │
│                ChatOllama  ──HTTP──►  192.168.1.50/v1          │
│                                                                │
│   get_session_history(session_id) → ChatMessageHistory (dict) │
└──────────────────────────────────────────────────────────────┘
```

**Componentes LangChain usados:**

- `ChatPromptTemplate.from_messages` — monta o prompt com system + histórico + input.
- `MessagesPlaceholder` — injeta o histórico de mensagens.
- `chain = prompt | llm` — LCEL (LangChain Expression Language).
- `RunnableWithMessageHistory` — envelopa a chain para persistir histórico por `session_id`.
- `ChatMessageHistory` — armazenamento in-memory do histórico.

---

## 3. Pré-requisitos

- Python 3.12+
- Acesso de rede ao endpoint do modelo (`192.168.1.50`)
- Credencial de API válida (`x-api-key`)

Dependências (extraídas do `venv`):

```
langchain-core==1.4.0
langchain-community==0.4.1
langchain-ollama==1.1.0
langchain-classic==1.0.7
langchain-text-splitters==1.1.2
ollama==0.6.2
pydantic==2.13.4
python-dotenv==1.2.2
```

> ⚠️ **Gap:** não existe `requirements.txt` nem `pyproject.toml` versionado no repositório.
> A reprodução do ambiente depende do `venv` local. Ver [Melhorias](#11-melhorias-sugeridas-roadmap).

---

## 4. Instalação

```bash
python3 -m venv venv
source venv/bin/activate

# Recomendado criar este arquivo (ver seção Melhorias)
pip install -r requirements.txt

# Ou manualmente, com as versões acima:
pip install langchain-core langchain-community langchain-ollama python-dotenv
```

---

## 5. Configuração

O modelo é instanciado em `app.py:11-19`:

```python
llm = ChatOllama(
    model="gemma3:12b",
    temperature=0,
    base_url="http://192.168.1.50/v1",
    headers={
        "x-api-key": "sk-indexacao-...",   # ⚠️ CREDENCIAL HARDCODED
        "Content-Type": "application/json"
    }
)
```

> 🔴 **Achado crítico:** `load_dotenv()` é chamado mas **nenhuma variável de ambiente é lida**.
> A chave de API está **hardcoded no código-fonte**. Para uma ferramenta de auditoria de
> segurança, isso é exatamente o tipo de finding que ela deveria reportar. Ver [Gaps](#10-gaps-identificados).

`.env` recomendado:

```env
AUDIT_MODEL=gemma3:12b
AUDIT_BASE_URL=http://192.168.1.50/v1
AUDIT_API_KEY=sk-...
```

---

## 6. Como Usar

```bash
source venv/bin/activate
python app.py
```

Fluxo interativo:

```
--- Security Audit Agent ---
Caminho do projeto para auditoria: /caminho/do/projeto
Nome do projeto: MeuApp
⏳ Analisando arquivos e gerando relatório...

==================================================
RELATÓRIO INICIAL:
==================================================
<relatório do modelo>

Você (ou 'sair'): existe risco de SQL injection?
AI: <resposta>

Você (ou 'sair'): sair
```

---

## 7. Referência do Código

### `carregar_contexto_projeto(diretorio)` — `app.py:62`
Percorre o diretório com `os.walk`, ignora `venv/.venv/node_modules/.git`, lê arquivos
das extensões permitidas e concatena tudo em uma única string com cabeçalhos
`--- ARQUIVO: <path> ---`. Tratamento de erro por arquivo (não interrompe a varredura).

### `get_session_history(session_id)` — `app.py:41`
Factory de histórico: retorna (ou cria) um `ChatMessageHistory` por `session_id`,
guardado no dict global `store`.

### `iniciar_auditoria()` — `app.py:84`
Orquestra a CLI: valida caminho, coleta nome, carrega contexto, faz a primeira invocação
(relatório) e entra no loop de chat. `session_id` fixo em `"audit_01"`.

### Objeto `executor` — `app.py:48`
`RunnableWithMessageHistory` envolvendo `chain = prompt | llm`, com chaves
`input` / `history` e config de sessão.

---

## 8. Fluxo de Execução

1. `iniciar_auditoria()` pede caminho e nome.
2. `carregar_contexto_projeto()` gera a string de contexto (todo o código).
3. **1ª invocação:** envia `input` genérico + `nome_projeto` + `dados_entrada` (todo o código).
   O modelo retorna o relatório inicial.
4. **Loop:** cada pergunta reenvia `dados_entrada="O contexto já foi enviado anteriormente."`,
   confiando que o histórico (`MessagesPlaceholder`) ainda carrega o código da 1ª mensagem.

---

## 9. Análise Crítica (Sênior LangChain)

### 🔴 9.1 — Descasamento de protocolo: `ChatOllama` vs endpoint `/v1`
Este é o achado arquitetural mais relevante. Os sinais — `base_url` terminando em **`/v1`**,
header **`x-api-key`** e chave no formato **`sk-...`** — indicam fortemente que o destino é um
**gateway OpenAI-compatible** (LiteLLM, vLLM, proxy de indexação etc.), **não** um servidor
Ollama nativo.

Porém `ChatOllama` (via cliente `ollama`) fala o **protocolo nativo do Ollama** (`/api/chat`),
não o protocolo OpenAI (`/v1/chat/completions`). Consequências prováveis:
- O cliente Ollama pode anexar suas próprias rotas a `base_url`, gerando caminhos inválidos.
- O parâmetro `headers=` no `ChatOllama` não é necessariamente repassado ao transporte HTTP
  da forma esperada (o canal correto seria `client_kwargs={"headers": {...}}`), então a
  autenticação `x-api-key` pode estar sendo **ignorada**.

**Recomendação:** se o endpoint é OpenAI-compatible, usar `ChatOpenAI`
(`langchain-openai`) com `base_url=".../v1"` e `api_key=...`. Se é Ollama nativo, remover o
`/v1` e usar a porta padrão (`http://192.168.1.50:11434`) e mover headers para `client_kwargs`.

### 🟠 9.2 — `RunnableWithMessageHistory` está subutilizado / em depreciação
- `session_id` é fixo (`"audit_01"`): toda a infra de multi-sessão (`store`, factory,
  `history_factory_config`) existe mas nunca é exercitada. Uma única sessão por processo.
- Em LangChain 1.x o padrão recomendado para memória é **LangGraph** (`MemorySaver`/checkpointers).
  `RunnableWithMessageHistory` ainda funciona, mas é a abordagem legada.

### 🟠 9.3 — Custo de contexto cresce sem controle
Todo o código vai numa única mensagem humana da 1ª chamada. Como o histórico é reenviado a
cada turno, **o repositório inteiro trafega novamente em todos os turnos do chat**. Em projetos
grandes isso: (a) estoura a janela de contexto do `gemma3:12b`, (b) torna cada resposta lenta e
cara. O comentário “para não estourar o limite de tokens” existe, mas **não há limite real** —
só se ignoram diretórios.

### 🟡 9.4 — Sem saída estruturada
Uma auditoria de segurança se beneficia enormemente de saída estruturada (severidade,
categoria OWASP/CWE, arquivo, linha, recomendação). Hoje a resposta é texto livre, difícil de
pós-processar, exportar (SARIF/JSON) ou integrar a CI. `langchain-text-splitters` está
instalado mas não é usado.

### 🟡 9.5 — Sem streaming
`executor.invoke()` é bloqueante: o usuário espera o relatório inteiro. `ChatOllama` suporta
`.stream()`, que melhoraria muito a UX para respostas longas.

### 🟡 9.6 — Robustez da varredura de arquivos
- `temperature=0` ✅ (bom para determinismo em auditoria).
- Não há limite de tamanho por arquivo nem total — um arquivo minificado/gerado pode dominar o contexto.
- Binários/arquivos enormes (lockfiles, builds) não são filtrados além das pastas ignoradas.
- O relatório não é persistido em disco (some quando o terminal fecha).

---

## 10. Gaps Identificados

| # | Gap | Severidade | Onde |
|---|-----|-----------|------|
| G1 | API key hardcoded no código-fonte | 🔴 Crítico | `app.py:16` |
| G2 | `load_dotenv()` chamado mas env nunca lido | 🔴 Crítico | `app.py:8` |
| G3 | Provável protocolo errado (`ChatOllama` × endpoint `/v1`) | 🔴 Crítico | `app.py:11-19` |
| G4 | Sem `requirements.txt` / `pyproject.toml` versionado | 🟠 Alto | raiz |
| G5 | Sem `.gitignore` (`venv/`, `.env` podem vazar) | 🟠 Alto | raiz |
| G6 | Contexto inteiro reenviado a cada turno (custo/limite) | 🟠 Alto | `app.py:123-130` |
| G7 | `session_id` fixo — multi-sessão morta | 🟡 Médio | `app.py:109,129` |
| G8 | Sem limite de tamanho de arquivo/contexto | 🟡 Médio | `app.py:62-82` |
| G9 | Sem saída estruturada / export (JSON/SARIF) | 🟡 Médio | geral |
| G10 | Sem streaming de resposta | 🟡 Médio | `app.py:103,123` |
| G11 | Sem testes, logging ou tratamento granular de erros | 🟡 Médio | geral |
| G12 | Sem persistência do relatório em disco | 🟢 Baixo | `app.py:115` |
| G13 | Sem README/docs de uso (resolvido por este arquivo) | 🟢 Baixo | raiz |

---

## 11. Melhorias Sugeridas (Roadmap)

### Curto prazo (segurança e higiene) — corrige G1, G2, G4, G5
1. **Mover segredos para `.env`** e ler com `os.getenv`. Adicionar `.env.example`.
2. Criar `.gitignore` com `venv/`, `.env`, `__pycache__/`.
3. Congelar dependências: `pip freeze > requirements.txt`.

```python
import os
from dotenv import load_dotenv
load_dotenv()

llm = ChatOllama(
    model=os.getenv("AUDIT_MODEL", "gemma3:12b"),
    temperature=0,
    base_url=os.getenv("AUDIT_BASE_URL"),
    client_kwargs={"headers": {"x-api-key": os.getenv("AUDIT_API_KEY")}},
)
```

### Médio prazo (arquitetura) — corrige G3, G6, G7, G10
4. **Confirmar o protocolo do endpoint.** Se OpenAI-compatible, migrar para `ChatOpenAI`:
   ```python
   from langchain_openai import ChatOpenAI
   llm = ChatOpenAI(model="gemma3:12b", temperature=0,
                    base_url=os.getenv("AUDIT_BASE_URL"),   # .../v1
                    api_key=os.getenv("AUDIT_API_KEY"))
   ```
5. **Migrar memória para LangGraph** (`MemorySaver` + `thread_id`) — padrão de 1.x —
   e usar um `session_id`/`thread_id` real por auditoria.
6. **Streaming** no relatório e no chat: trocar `.invoke()` por `.stream()`.

### Longo prazo (escala e produto) — corrige G6, G8, G9
7. **RAG / indexação** para projetos grandes: usar `langchain-text-splitters` + um vector
   store (FAISS/Chroma) e recuperar apenas os trechos relevantes por pergunta, em vez de
   enfiar o repositório inteiro no prompt. Resolve limite de contexto e custo de uma vez.
8. **Saída estruturada** com `llm.with_structured_output(Finding)` (Pydantic), gerando
   findings com `severidade / categoria_owasp / cwe / arquivo / linha / recomendação`,
   exportáveis para JSON ou **SARIF** (integra com GitHub Code Scanning / CI).
9. **Persistir o relatório** (`audit_<projeto>_<data>.md`) e adicionar `logging` estruturado.
10. **Testes** (pytest) para `carregar_contexto_projeto` (filtros, limites, encoding) e um
    smoke test mockando o LLM.

### Visão de produto
- Limites configuráveis (tamanho máx. por arquivo, total de tokens, lista de extensões).
- Modo não-interativo / CLI com flags (`--path`, `--name`, `--out`) para rodar em pipelines.
- Cache de prompt para reduzir custo em re-execuções.
```
