# Design do Agent & Decisões — Auditor-IA

Este documento registra as decisões de design e como elas refletem **boas práticas
de LangChain/LangGraph**.

## 1. Por que LangGraph (e não um AgentExecutor monolítico)?

Auditoria é um processo com **etapas distintas, dependências claras e um ponto de
interação humana**. LangGraph modela isso como um grafo explícito de estados, o que traz:

- **Controle de fluxo determinístico** — a ordem descoberta → esclarecimento →
  plano → auditoria → síntese → relatório é garantida pelas arestas do grafo.
- **Human-in-the-loop nativo** — `interrupt`/`Command(resume=...)` com checkpointer.
- **Observabilidade** — cada nó é um passo inspecionável (`stream_mode="updates"`).
- **Retomada** — com checkpointer persistente, uma auditoria pode ser pausada e retomada.

Um `AgentExecutor` genérico seria opaco e difícil de pausar para conversa.

## 2. Padrão "orquestrador + investigadores"

O grafo principal é o **orquestrador**; a fase de auditoria delega a
**sub-agents ReAct** especializados (um por dimensão). Isso é o padrão
*supervisor/worker*:

- Cada investigador tem um **prompt focado** e o **mesmo conjunto de ferramentas**.
- A separação evita que um único prompt gigante tente cobrir tudo (o que degrada a qualidade).
- Facilita adicionar/remover dimensões sem tocar no restante do grafo.

## 3. Saída estruturada em vez de parsing de texto

Todos os pontos de decisão usam **saída estruturada Pydantic**:

- `with_structured_output(ClarifyingQuestions)` — perguntas de esclarecimento.
- `with_structured_output(AuditPlan)` — seleção de dimensões.
- `create_react_agent(..., response_format=DimensionResult)` — achados.

Vantagens: validação automática, retries do provedor em caso de schema inválido,
zero parsing frágil de string. É a prática recomendada atual do LangChain.

## 4. Ferramentas read-only e seguras

- O agent **audita, não corrige** → todas as ferramentas são somente leitura.
- Escopo restrito à raiz do projeto com **bloqueio de path traversal**.
- Limites de tamanho/quantidade → controle de custo e latência.

Isso segue o princípio de **menor privilégio** para ferramentas de agent.

## 5. Prompts centralizados e versionáveis

Todos os prompts vivem em `prompts/templates.py`, separados da lógica. Isso permite
iterar em prompt engineering sem alterar código de orquestração e facilita revisão.

Princípios embutidos na persona (`SYSTEM_PERSONA`):
- **Evidência obrigatória** — reduz alucinação ("se não verificou, não afirme").
- **Precisão > volume** — evita inflar o relatório com achados especulativos.
- **Sempre acionável** — todo achado exige recomendação.

## 6. Determinismo e reprodutibilidade

Temperatura padrão `0`. Auditorias devem ser o mais reproduzíveis possível; a
variabilidade criativa não é desejável aqui.

## 7. Robustez

- Falha de um investigador é **isolada** (try/except por dimensão).
- Validação de dimensões contra o enum, com _fallback_ para um conjunto padrão.
- Serialização JSON-safe do estado (compatível com checkpointers persistentes).
- Limites de recursão nos sub-agents (evita loops infinitos de tool-calling).

## 8. Decisões deliberadamente adiadas (trade-offs)

| Decisão | v0.1 | Por quê | Evolução |
| --- | --- | --- | --- |
| Paralelismo de dimensões | Sequencial | Previsibilidade de custo e logs legíveis | *Send API* (ROADMAP) |
| Checkpointer | `MemorySaver` | Simplicidade | `SqliteSaver`/`Postgres` |
| Scanners externos | Ausente | Manter zero-dependência de toolchain | Integração opcional |
| Multi-provider | ✅ via `init_chat_model` | Flexibilidade sem lock-in de provedor | Presets por provedor |

## 9. Extensibilidade

- **Nova dimensão:** adicione ao enum `AuditDimension` e a `DIMENSION_GUIDANCE`. O
  planejador passa a considerá-la automaticamente.
- **Nova ferramenta:** adicione em `make_project_tools` — todos os investigadores a recebem.
- **Novo formato de relatório:** adicione um renderer em `report/` e chame no `report_node`.
- **Outro LLM:** defina `AUDITOR_PROVIDER`/`AUDITOR_MODEL` (ou `--provider`/`--model`).
  A factory em `llm.py` usa `init_chat_model`, então qualquer provedor suportado
  pelo LangChain funciona sem alteração de código — basta instalar o pacote.

## 10. Boas práticas aplicadas (checklist)

- [x] Grafo explícito com estado tipado e reducers.
- [x] Human-in-the-loop com `interrupt` + checkpointer.
- [x] Isolamento da geração de perguntas do ponto de interrupção (evita chamada dupla).
- [x] Saída estruturada Pydantic em todos os pontos de decisão.
- [x] Sub-agents ReAct com ferramentas e `response_format`.
- [x] Ferramentas de menor privilégio (read-only, escopadas).
- [x] Prompts centralizados e versionáveis.
- [x] Configuração externalizada (12-factor).
- [x] Tratamento de falhas por etapa.
- [x] Testes offline que não dependem do LLM.
