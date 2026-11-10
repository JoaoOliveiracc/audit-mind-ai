# Provider Extras Specification (G47)

## Problem Statement
`google_vertexai`, `cohere`, `together` and `fireworks` are advertised in `config.PROVIDER_PACKAGE`
(and `auditor providers`) but have no extra in `pyproject.toml`: no install path, no version floor.

## Decisions
| Decision | Default | Rationale | Confirmed? |
| -------- | ------- | --------- | ---------- |
| Approach | add extras `vertexai`, `cohere`, `together`, `fireworks`; `all-providers` unchanged | User decision. | y |
| Floor rule | first release whose metadata **declares** `langchain-core>=1.0` (PyPI `requires_dist`) | "Resolves with core 1.4" is not enough: `vertexai==2.1.2` resolves only because it declares an open-ended `>=0.3.76`. | y (agent) |
| Floors | `langchain-google-vertexai>=3.0`, `langchain-cohere>=0.5`, `langchain-together>=0.4`, `langchain-fireworks>=1.0` | From PyPI metadata (vertexai 3.0.0 `>=1.0.0,<2`; cohere 0.5.0 `>=1.0.0,<2`; together 0.4.0 `>=1.2.22,<2`; fireworks 1.0.0 `>=1.0.0,<2`); each also resolves with core 1.4.8 (`pip --dry-run`). | y (agent) |

## Acceptance Criteria
1. **PROV-01** Every package in `config.PROVIDER_PACKAGE` SHALL be installable from `pyproject.toml` (core dependency or some extra).
2. **PROV-02** The 4 new extras SHALL use exactly the floors above (DEP-01 floor table extended).
3. **PROV-03** `pip install --dry-run -e ".[vertexai,cohere,together,fireworks]"` SHALL resolve (recorded).
4. **PROV-04** README's provider install line SHALL list the new extras.

## Traceability
| ID | Where | Status |
| -- | ----- | ------ |
| PROV-01..02, PROV-04 | `tests/test_ci_config.py` | Verified |
| PROV-03 | validation record | Verified |

## Execution notes
- Red phase: DEP-01 (extended table), PROV-01 and PROV-04 failed before the change.
- PROV-03: `pip install --dry-run --ignore-installed -e ".[vertexai,cohere,together,fireworks]"` → exit 0; resolves vertexai 3.2.5, cohere 0.6.0, together 0.4.0, fireworks 1.7.3 with langchain-core 1.7.7.
- Floor evidence (PyPI `requires_dist`): vertexai 2.1.2 `langchain-core>=0.3.76` (open-ended, pre-1.x line) vs 3.0.0 `>=1.0.0,<2.0.0`; cohere 0.4.6 `<0.4.0` vs 0.5.0 `>=1.0.0,<2.0`; together 0.3.1 `<0.4.0` vs 0.4.0 `>=1.2.22,<2`; fireworks 0.3.0 `<1.0.0` vs 1.0.0 `>=1.0.0,<2.0.0`.
