# Vulnerable Dependencies & Runtimes Specification (G48)

## Problem Statement

The agent cannot reliably tell whether a project uses a vulnerable dependency or an unsupported
runtime: it consults no vulnerability database (the LLM judges "vulnerable dependencies" from
memory, which predates recent CVEs), and `.lock` files are treated as binary, so `composer.lock`,
`yarn.lock`, `poetry.lock`, `uv.lock`… are never read. Vulnerabilities in a runtime's core (PHP
interpreter, Node.js) can't be *found* by a project auditor, but *using an affected/unsupported
runtime version* can be detected.

## Goals
- [ ] Opt-in, deterministic scan: exact versions from lockfiles → OSV.dev advisories (CVE/GHSA ids, severity, fixed version), and declared runtime → endoflife.date (EOL / behind latest patch).
- [ ] Zero LLM tokens; findings are verifiable (cite the lockfile line).
- [ ] Never sends code, and never sends private package names.

## Out of Scope
| Feature | Reason |
| ------- | ------ |
| Gemfile.lock, Cargo.lock, Go, NuGet, Maven | User: Node + PHP + Python first; parser registry makes them additive later. |
| Runtime core CVE lists (nodejs/security-wg) | User: EOL + patch only (no index; PHP/Python have no structured feed). |
| Running `npm/composer/pip-audit` locally | Not requested. |
| Offline/mirrored OSV database | Not requested. |

## Assumptions & Decisions
| Decision | Default | Rationale | Confirmed? |
| -------- | ------- | --------- | ---------- |
| Ecosystems | npm (`package-lock.json` v2/v3, `yarn.lock` v1 + berry, `pnpm-lock.yaml`), Packagist (`composer.lock`), PyPI (`poetry.lock`, `uv.lock`, `Pipfile.lock`, `requirements*.txt` with `==` pins) | User decision. | y |
| Runtime | Node, PHP, Python via endoflife.date `/api/v1/products/{slug}`: EOL and behind-latest-patch | User decision. | y |
| Activation | off by default; `AUDITOR_VULN_SCAN=true`, CLI `--vuln-scan/--no-vuln-scan`, API `vuln_scan` field, web form checkbox | User decision (privacy; Ollama users expect zero egress). | y |
| Grouping | one finding per `ecosystem:name@version`, listing every advisory; severity = max; dev-only deps → `info` | User decision. | y |
| Private packages | skipped (never queried) per the per-format rules in LOCK-03; counted in stats | Querying `@acme/internal` leaks private names. Rules reviewed (spec review): GitHub URLs can't tell public from private; yarn berry/pnpm locks don't store the registry host. | y (agent) |
| Severity | OSV `database_specific.severity` (GHSA: LOW/MODERATE/HIGH/CRITICAL) → else CVSS v3.x base score from the vector → else `medium` with a note | Verified fields on a real OSV record. | y (agent) |
| Graph placement | new deterministic node `dependency_scan` **after** `audit` (audit overwrites `findings`), before `verify` | Findings cite the exact lockfile line, so `verify` confirms them; adversarial judge skips them (factual). | y (agent) |
| Failure | network/API error → scan stats record the error, audit continues, no partial guesses | External dependency must not break audits. | y (agent) |

**Open questions:** none.

## User Stories & Acceptance Criteria

### P1: Lockfile parsing ⭐ MVP
1. **LOCK-01** For each supported lockfile, the parser SHALL return `Dependency(ecosystem, name, version, dev, private, file, line)` for every installed package. `line` (1-based) is the line carrying that package's version: `package-lock.json`/`composer.lock` → the `"version"` line inside the package's block; `yarn.lock` (v1 and berry) → the `version` line of the entry; `pnpm-lock.yaml` → the package key line (`/name@version` or `name@version:`); `poetry.lock`/`uv.lock` → the `version = …` line of its `[[package]]`; `Pipfile.lock` → the `"version"` line; `requirements*.txt` → the `name==version` line itself.
2. **LOCK-02** `dev` SHALL be true only when the lockfile marks the package as development-only (`package-lock` `dev: true`, `composer.lock` `packages-dev`, `poetry.lock` group/category `dev`, `Pipfile.lock` `develop`, `pnpm` `dev: true`, `uv` dev-only groups) **or** the file is `requirements-dev*.txt`, `requirements-test*.txt` or `dev-requirements*.txt`.
3. **LOCK-03** A package SHALL be marked `private` (never queried) when any of these holds — conservative by design (doubt ⇒ private):
   - **npm (all formats):** a git/file/link/workspace/tarball-URL source; `package-lock`/`yarn v1` `resolved` host ≠ `registry.npmjs.org`/`registry.yarnpkg.com`; the package's scope (or the default registry) is mapped to a non-public host in the project's `.npmrc` (`registry=`, `@scope:registry=`) or `.yarnrc.yml` (`npmRegistryServer`, `npmScopes.<scope>.npmRegistryServer`) — required because yarn berry and pnpm locks don't record the registry host;
   - **composer.lock:** the package lacks `"notification-url": "https://packagist.org/downloads/"` (GitHub dist URLs can't distinguish public from private repos);
   - **poetry.lock / uv.lock:** a `source` other than PyPI (`https://pypi.org/simple` / no explicit source); **Pipfile.lock:** a package `index` whose `_meta.sources` URL is not PyPI;
   - **requirements*.txt:** if the file declares `--index-url`/`--extra-index-url`/`-i` pointing outside PyPI, the **whole file** is skipped (origin per package is undeterminable) and recorded in stats; VCS/URL/path requirements are private.
4. **LOCK-04** Malformed/unknown-version lockfiles SHALL NOT raise: the file is skipped and recorded in stats as a parse error.
5. **LOCK-05** `.lock` SHALL no longer be treated as binary (investigators can read/search lockfiles).

### P1: OSV lookup ⭐ MVP
6. **OSV-01** Public deps SHALL be queried with `POST /v1/querybatch` (chunks ≤ 500, honoring `next_page_token`), then each distinct advisory fetched once via `GET /v1/vulns/{id}`. PyPI names SHALL be normalized per PEP 503 (lowercase; runs of `-`, `_`, `.` → `-`) before querying and grouping; npm and Packagist names are compared case-sensitively as written.
7. **OSV-02** Per advisory: id, CVE aliases, summary, severity (per the decision above), and the fixed version of the range that contains the installed version (or "no fix published").
8. **OSV-03** Only hosts `api.osv.dev` and `endoflife.date` over HTTPS SHALL be contacted, with a 15 s timeout per request; payloads contain only ecosystem, package name and version. Each response body SHALL be read in streaming with a **5 MB cap** (over the cap → that request counts as an error). At most **10 000** public packages per scan; beyond that the rest are not queried and stats set `truncated: true`.

### P1: Findings ⭐ MVP
9. **FND-01** One finding per vulnerable package@version — **across all lockfiles** (monorepos): it cites the first occurrence (by relative path order) and the description lists the other occurrences; `dimension="dependencies"`, `source="osv"`, title `"<name>@<version> com N vulnerabilidade(s) conhecida(s)"`, severity = max (dev → `info`), `file`/`line` = lockfile line, `evidence` = that exact line, description listing every advisory id (+ CVE), recommendation "Atualize para ≥ <highest fixed>" (or "sem correção publicada; avalie substituir/mitigar").
10. **FND-02** These findings SHALL pass `verify` (evidence present on disk) and SHALL NOT be sent to the adversarial judge.

### P1: Runtime ⭐ MVP
11. **RT-01** Declared runtime SHALL be detected from: Node `.nvmrc`, `.node-version`, `package.json engines.node`, Dockerfile `FROM node:<tag>`; PHP `composer.json require.php`, Dockerfile `FROM php:<tag>`; Python `.python-version`, `pyproject requires-python`, Dockerfile `FROM python:<tag>`.
12. **RT-02** Cycle and exactness per runtime — Node: cycle = major (`20`), exact = `major.minor[.patch]` (`20.11`, `20.11.1`); PHP/Python: cycle = `major.minor` (`8.1`, `3.11`), exact = `major.minor.patch` (`8.1.27`, `3.11.4`).
    - cycle-only declaration (e.g. `node:20-alpine`, `php:8.1-fpm`, `.python-version` `3.11`): cycle EOL → `high`; otherwise no finding;
    - exact declaration: cycle EOL → `high`; else lower than the cycle's `latest` → `medium`;
    - tags without a version (`lts`, `latest`, `alpine`, `current`) → unknown (RT-04).
13. **RT-03** Range (`>=18`, `^8.1`, `>=3.9`): if its minimum cycle is EOL → `medium` ("a faixa permite runtime sem suporte").
14. **RT-04** Unknown cycle/tag → no finding (recorded in stats). Findings: `source="endoflife"`, file/line/evidence = the declaring line.
15. **RT-05** Each declaration is evaluated independently (e.g. `.nvmrc` `18` and `engines.node >=20` → up to two findings), never merged.

### P1: Activation, stats, interfaces ⭐ MVP
16. **CFG-01** Disabled by default; enabled per run by `AUDITOR_VULN_SCAN`, CLI `--vuln-scan/--no-vuln-scan` (flag wins), API `CreateAuditRequest.vuln_scan` (request wins). When disabled: no network call at all.
17. **CFG-02** State `dependency_scan` stats: `enabled, packages, queried, skipped_private, vulnerable, runtime_findings, errors[]`; emitted as SSE event `dependency_scan`; shown in the Markdown/HTML report and the CLI summary.
18. **UI-01** The web start form SHALL have a "Verificar dependências vulneráveis (envia nomes e versões ao OSV.dev)" checkbox, off by default, sent as `vuln_scan`.
19. **RPT-01** (spec review) The Markdown/HTML report and the CLI summary SHALL state the scan status explicitly: disabled → "Verificação de dependências desativada (AUDITOR_VULN_SCAN)"; errors or `truncated` → "Varredura de dependências incompleta" + the reasons; enabled and clean → "Nenhuma vulnerabilidade conhecida nas N dependências consultadas". (T10 precision fix) enabled with findings and no errors → "N pacote(s) vulnerável(is) entre M dependências consultadas"; every enabled status appends "(K privada(s) não consultada(s))" when K > 0. Absence of findings must never read as "secure" by omission.
20. **DUP-01** (spec review) When the scan is enabled for the run, every investigator prompt SHALL include: "Vulnerabilidades conhecidas (CVEs) de dependências já são verificadas por uma varredura determinística — não as reporte; foque em uso inseguro das dependências no código." When disabled, prompts are unchanged.

### P1: End-to-end
21. **E2E-05** Offline e2e (fake HTTP transport): a fixture project with a vulnerable `package-lock.json` entry, a private scoped package and `.nvmrc` on an EOL cycle yields one OSV finding (verified, not judged), one runtime finding, `skipped_private == 1`, and zero real network calls.

## Traceability
(see tasks.md)

## Review log
- 2026-11-10 spec review (10 items): LOCK-03 per-format private rules (composer notification-url; .npmrc/.yarnrc.yml; requirements index → skip file); RPT-01 explicit scan status; DUP-01 no LLM duplicates; OSV-03 5 MB / 10 000 caps; OSV-01 PEP 503; RT-02 cycle vs exact per runtime; RT-05 independent declarations; LOCK-02 requirements dev names; LOCK-01 line per format; FND-01 cross-lockfile grouping.
