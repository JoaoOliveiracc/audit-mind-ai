# Especificação Funcional — Auditor-IA

## 1. Objetivo

Fornecer um agent autônomo, porém colaborativo, capaz de **auditar qualquer projeto
de desenvolvimento** independentemente da linguagem ou framework, produzindo um
relatório completo, acionável e fundamentado em evidências.

## 2. Escopo

### 2.1 Dentro do escopo
- Análise estática do código-fonte e artefatos de configuração de um diretório.
- Detecção automática de stack (linguagens, frameworks, gerenciadores de pacote).
- Diálogo de esclarecimento com o usuário (human-in-the-loop).
- Auditoria multidimensional (ver §4).
- Pontuação de saúde e priorização de riscos.
- Relatório em Markdown e HTML.

### 2.2 Fora do escopo (v0.1)
- Execução de código do projeto auditado (sandboxing dinâmico).
- Modificação/correção automática de código (o agent é read-only).
- Integração com scanners externos (Semgrep, Trivy, etc.) — planejado (ver ROADMAP).
- Análise de repositórios remotos sem clone local prévio.

## 3. Personas e casos de uso

| Persona | Caso de uso |
| --- | --- |
| Tech Lead | Avaliar a saúde de um projeto antes de assumir manutenção. |
| Desenvolvedor | Revisão pré-produção com foco em segurança. |
| Gestor técnico | Relatório executivo do estado de um produto. |
| Auditor externo | Due diligence técnica de um codebase de terceiro. |

## 4. Dimensões de auditoria

O agent seleciona dinamicamente as dimensões aplicáveis ao projeto:

1. **Segurança** — segredos hardcoded, injeção, authn/authz, cripto, exposição de dados.
2. **Qualidade de código** — complexidade, duplicação, tratamento de erros, code smells.
3. **Arquitetura** — acoplamento/coesão, camadas, padrões, escalabilidade estrutural.
4. **Dependências** — versões, licenças, dependências abandonadas, locks ausentes.
5. **Testes** — existência, organização, cobertura aparente, tipos de teste.
6. **Documentação** — README, setup, docs de API, ADRs, onboarding.
7. **Performance** — N+1, I/O bloqueante, cache, algoritmos ineficientes.
8. **CI/CD** — pipelines, gates de qualidade, estratégia de release.
9. **Observabilidade** — logging, métricas, tracing, health checks.
10. **Compliance** — LGPD/GDPR, dados pessoais, trilhas de auditoria.

## 5. Requisitos funcionais

- **RF-01** O agent detecta a stack do projeto automaticamente.
- **RF-02** O agent gera 0–5 perguntas de esclarecimento contextualizadas e aguarda resposta.
- **RF-03** O usuário pode pular qualquer pergunta ou toda a fase (`--no-questions`).
- **RF-04** O agent seleciona apenas dimensões aplicáveis ao projeto.
- **RF-05** Cada achado contém: dimensão, título, severidade, descrição, recomendação, confiança e (quando aplicável) arquivo/linha/evidência.
- **RF-06** O agent calcula uma pontuação de saúde 0–100 a partir das severidades.
- **RF-07** O agent produz um resumo executivo consolidado.
- **RF-08** O relatório é emitido em Markdown e HTML.

## 6. Requisitos não funcionais

- **RNF-01 (Segurança)** Ferramentas são read-only e restritas à raiz do projeto (bloqueio de path traversal).
- **RNF-02 (Robustez)** A falha de um investigador não interrompe as demais dimensões.
- **RNF-03 (Portabilidade)** Funciona com qualquer stack; sem dependência de toolchain do projeto.
- **RNF-04 (Configurabilidade)** Modelo, limites e diretórios configuráveis por env.
- **RNF-05 (Determinismo)** Temperatura padrão 0 para reprodutibilidade razoável.
- **RNF-06 (Custo/limites)** Limites de arquivos, tamanho e passos de raciocínio evitam explosão de custo.

## 7. Critérios de aceite

- Executar `auditor audit <dir>` em um projeto de qualquer stack produz relatórios `.md` e `.html` sem erros.
- Achados críticos (ex.: segredo hardcoded) são detectados e classificados como `critical`.
- O relatório HTML abre em qualquer navegador sem recursos externos.
- Os testes de fumaça (`pytest`) passam offline.

## 8. Entradas e saídas

**Entrada:** caminho de um diretório de projeto + objetivo opcional + respostas de esclarecimento.

**Saída:**
- `audit-reports/auditoria-<timestamp>.md`
- `audit-reports/auditoria-<timestamp>.html`
- Resumo no terminal (pontuação + distribuição de achados + caminhos).
