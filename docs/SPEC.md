# Functional Specification — Audit Mind AI

## 1. Objective

Provide an autonomous yet collaborative agent capable of **auditing any development
project** regardless of language or framework, producing a complete, actionable
report grounded in evidence.

## 2. Scope

### 2.1 In scope
- Static analysis of source code and configuration artifacts of a directory.
- Automatic stack detection (languages, frameworks, package managers).
- Clarification dialogue with the user (human-in-the-loop).
- Multidimensional audit (see §4).
- Health score and risk prioritization.
- Report in Markdown and HTML, plus SARIF 2.1.0 export.
- Deterministic evidence verification and optional adversarial review of findings.
- Local web interface (FastAPI + SSE backend, Vite/React frontend).

### 2.2 Out of scope (v0.1)
- Execution of the audited project's code (dynamic sandboxing).
- Automatic code modification/correction (the agent is read-only).
- Integration with external scanners (Semgrep, Trivy, etc.) — planned (see ROADMAP).
- Analysis of remote repositories without a prior local clone.

## 3. Personas and use cases

| Persona | Use case |
| --- | --- |
| Tech Lead | Assess the health of a project before taking over maintenance. |
| Developer | Pre-production review focused on security. |
| Technical manager | Executive report on the state of a product. |
| External auditor | Technical due diligence of a third-party codebase. |

## 4. Audit dimensions

The agent dynamically selects the dimensions applicable to the project:

1. **Security** — hardcoded secrets, injection, authn/authz, crypto, data exposure.
2. **Code quality** — complexity, duplication, error handling, code smells.
3. **Architecture** — coupling/cohesion, layers, patterns, structural scalability.
4. **Dependencies** — versions, licenses, abandoned dependencies, missing locks.
5. **Tests** — existence, organization, apparent coverage, test types.
6. **Documentation** — README, setup, API docs, ADRs, onboarding.
7. **Performance** — N+1, blocking I/O, caching, inefficient algorithms.
8. **CI/CD** — pipelines, quality gates, release strategy.
9. **Observability** — logging, metrics, tracing, health checks.
10. **Compliance** — LGPD/GDPR, personal data, audit trails.

## 5. Functional requirements

- **RF-01** The agent detects the project's stack automatically.
- **RF-02** The agent generates 0–5 contextualized clarification questions and waits for a response.
- **RF-03** The user can skip any question or the entire phase (`--no-questions`).
- **RF-04** The agent selects only the dimensions applicable to the project.
- **RF-05** Each finding contains: dimension, title, severity, description, recommendation, confidence and (when applicable) file/line/evidence.
- **RF-06** The agent computes a health score of 0–100 from the severities.
- **RF-07** The agent produces a consolidated executive summary.
- **RF-08** The report is emitted in Markdown and HTML.
- **RF-09** Findings are also exported as SARIF 2.1.0 (GitHub Code Scanning compatible).
- **RF-10** Every finding citing a file is checked on disk; findings whose evidence cannot be located are discarded.
- **RF-11** (optional) An adversarial LLM judge tries to refute findings at or above a severity threshold.
- **RF-12** The audit can be driven through a local HTTP API with SSE progress and human-in-the-loop answers.

## 6. Non-functional requirements

- **RNF-01 (Security)** Tools are read-only and restricted to the project root (path traversal blocking).
- **RNF-02 (Robustness)** The failure of one investigator does not interrupt the other dimensions.
- **RNF-03 (Portability)** Works with any stack; no dependency on the project's toolchain.
- **RNF-04 (Configurability)** Model, limits and directories configurable via env.
- **RNF-05 (Determinism)** Default temperature 0 for reasonable reproducibility.
- **RNF-06 (Cost/limits)** Limits on files, size and reasoning steps prevent cost explosion.
- **RNF-07 (Untrusted input)** The audited code is treated as untrusted: reports are escaped (no stored XSS) and tools never write.
- **RNF-08 (Concurrency)** Investigators run in parallel with a configurable limit; concurrent audits may use different providers.

## 7. Acceptance criteria

- Running `auditor audit <dir>` on a project of any stack produces `.md`, `.html` and `.sarif` reports without errors.
- Critical findings (e.g. hardcoded secret) are detected and classified as `critical`.
- The HTML report opens in any browser without external resources.
- The smoke tests (`pytest`) pass offline.

## 8. Inputs and outputs

**Input:** path of a project directory + optional objective + clarification responses.

**Output:**
- `audit-reports/auditoria-<timestamp>-<id8>.md`
- `audit-reports/auditoria-<timestamp>-<id8>.html`
- `audit-reports/auditoria-<timestamp>-<id8>.sarif`
- Terminal summary (score + finding distribution + paths).
