# Arquitetura — Auditor-IA

## 1. Visão geral

O Auditor-IA é um **grafo de estados (LangGraph)** onde cada nó é uma etapa da
auditoria. O estado é compartilhado e acumulado ao longo do fluxo. A fase de
auditoria delega a **sub-agents ReAct** (um por dimensão), que exploram o código
com ferramentas read-only e retornam achados estruturados.

```
                    ┌─────────────┐
      START ───────▶│  discovery  │  varre o projeto, detecta stack + inventário
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │plan_questions│ LLM gera perguntas de esclarecimento
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │   clarify   │ ⏸ interrupt → usuário responde (human-in-the-loop)
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │  planning   │ LLM seleciona dimensões aplicáveis
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐   para cada dimensão:
                    │    audit    │   create_react_agent(tools) → DimensionResult
                    └──────┬──────┘   (read_file, list_directory, search_code)
                           ▼
                    ┌─────────────┐
                    │  synthesis  │ pontuação de saúde + resumo executivo
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │   report    │ Markdown + HTML → disco
                    └──────┬──────┘
                           ▼
                          END
```

## 2. Componentes

| Módulo | Responsabilidade |
| --- | --- |
| `config.py` | Configurações via `pydantic-settings` (env / `.env`). |
| `llm.py` | Fábrica memoizada do `ChatAnthropic`. |
| `state.py` | `AuditState` (TypedDict + reducers) e modelos Pydantic de domínio. |
| `tools/project.py` | Detecção de stack e construção do inventário. |
| `tools/filesystem.py` | Ferramentas read-only escopadas (leitura/listagem/busca). |
| `prompts/templates.py` | Todos os prompts, centralizados. |
| `nodes/*` | Um arquivo por nó do grafo. |
| `graph.py` | Montagem e compilação do grafo. |
| `report/renderer.py` | Renderização Markdown e HTML (Jinja2). |
| `cli.py` | Interface de terminal (Typer + Rich) e loop de interrupção. |

## 3. Estado do grafo

`AuditState` é um `TypedDict` com _reducers_ anotados:

- `messages: Annotated[list, add_messages]` — histórico de conversa.
- `findings: Annotated[list, operator.add]` — acumula achados.
- `dimension_summaries: Annotated[list, operator.add]` — acumula resumos.

Os demais campos são substituídos por atribuição direta (última escrita vence).
Enums (ex.: `Severity`) são serializados para string via `model_dump(mode="json")`
para manter o estado JSON-serializável e compatível com checkpointers persistentes.

## 4. Human-in-the-loop

O nó `clarify` chama `interrupt(payload)`. Como o `interrupt` **re-executa o nó do
início** ao retomar, a geração de perguntas (que faz chamada ao LLM) foi isolada no
nó anterior `plan_questions`, evitando chamadas duplicadas. A retomada ocorre via
`Command(resume=answers)` disparado pelo CLI.

Um **checkpointer** é obrigatório para o `interrupt` funcionar. A v0.1 usa
`MemorySaver` (em memória). Para persistência entre execuções, troque por
`SqliteSaver`/`PostgresSaver` em `build_graph`.

## 5. Sub-agents ReAct (fase de auditoria)

Cada dimensão é auditada por um agent criado com `create_react_agent`:

- **Ferramentas:** `read_file`, `list_directory`, `search_code` (escopadas à raiz).
- **`response_format=DimensionResult`:** força saída estruturada validada por Pydantic.
- **`recursion_limit`:** limita os passos de raciocínio (env `AUDITOR_MAX_INVESTIGATOR_STEPS`).
- **Isolamento de falhas:** exceção em uma dimensão é capturada e registrada, sem abortar as demais.

> **Nota de evolução:** os investigadores rodam sequencialmente na v0.1 para
> previsibilidade de custo. A paralelização via *Send API* do LangGraph está
> mapeada no ROADMAP.

## 6. Segurança das ferramentas

`_safe_resolve` resolve caminhos sob a raiz e rejeita qualquer alvo fora dela
(proteção contra path traversal, ex.: `../../etc/passwd`). Arquivos binários e
acima de `AUDITOR_MAX_FILE_BYTES` são ignorados. Diretórios de build/deps
(`node_modules`, `.git`, `venv`, etc.) são pulados na varredura.

## 7. Pontuação de saúde

`compute_health_score` parte de 100 e subtrai pesos por severidade
(`critical=40, high=20, medium=8, low=3, info=0`), com piso em 0. É um indicador
heurístico para leitura executiva, não uma métrica formal.

## 8. Fluxo de dados (resumo)

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
