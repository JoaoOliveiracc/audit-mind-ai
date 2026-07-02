# Roadmap — Auditor-IA

## v0.1 (atual) ✅
- Grafo LangGraph completo (discovery → clarify → planning → audit → synthesis → report).
- Human-in-the-loop via `interrupt`.
- Investigadores ReAct por dimensão com saída estruturada.
- Detecção de stack agnóstica.
- Ferramentas read-only e seguras.
- Relatório Markdown + HTML.
- CLI interativo (Typer + Rich).
- Testes de fumaça offline.

## v0.2 — Escala e desempenho
- [ ] **Paralelizar investigadores** via *Send API* do LangGraph (fan-out por dimensão).
- [ ] **Checkpointer persistente** (`SqliteSaver`) para pausar/retomar auditorias.
- [ ] Cache de leituras de arquivo entre dimensões.
- [ ] Sumarização/seleção inteligente de arquivos em projetos muito grandes (map-reduce).

## v0.3 — Profundidade de análise
- [ ] Integração opcional com scanners externos (Semgrep, Trivy, gitleaks, pip-audit/npm-audit).
- [ ] Reconciliação: achados de scanner + achados do LLM, com deduplicação.
- [ ] Verificação adversarial de achados (segundo agent tenta refutar cada achado).
- [ ] Análise de histórico Git (hotspots, autores, churn).

## v0.4 — Experiência e integração
- [x] Camada de API (FastAPI) reutilizando o mesmo grafo — **entregue (F1–F3)**: endpoints, SSE, checkpointer SQLite e human-in-the-loop. Ver [`FRONTEND_SPEC.md`](FRONTEND_SPEC.md).
- [x] Exportação JSON estruturada de achados — **entregue** (`GET /audits/{id}/findings`).
- [ ] Frontend web (React + Next.js) consumindo a API — fases F4–F6.
- [ ] Ação de GitHub / GitLab (auditoria em PR com comentários inline).
- [ ] Comparação entre auditorias (diff de saúde ao longo do tempo).

## v0.5 — Governança
- [x] Factory multi-provider de LLM (`init_chat_model`) configurável por env — **entregue** (Anthropic, OpenAI, Google, Groq, Mistral, DeepSeek, Ollama, Bedrock, …).
- [ ] Perfis de auditoria (ex.: "OWASP", "LGPD", "pré-produção") como presets.
- [ ] Políticas configuráveis de severidade e gates de aprovação.
- [ ] Trilha de auditoria assinada (proveniência dos achados).

## Ideias em avaliação
- Modo "chat com o relatório" (perguntas sobre os achados após a auditoria).
- Priorização por esforço estimado de correção.
- Estimativa de dívida técnica em horas.
