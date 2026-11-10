# Dependency Floors & Single Source Specification (G40, remainder)

## Problem Statement

`requirements.txt` duplicates the core of `pyproject.toml` (without extras) and has drifted before.
Provider floors are pre-1.0 (`langchain-anthropic>=0.3.0` in core; `>=0.2` / `google-genai>=2.0`
in extras) while the project requires `langchain-core>=1.4`: `langchain-anthropic==0.3.22` is
**not installable** with `langchain-core==1.4.8` (verified with `pip --dry-run`) — the floor promises
something that doesn't work; installs only succeed because the resolver happens to pick 1.x.

## Out of Scope
| Feature | Reason |
| ------- | ------ |
| Lock file | User chose to remove `requirements.txt`, not replace it. |
| Upper bounds on providers | Not requested; CI resolves latest. |

## Assumptions
| Decision | Default | Rationale | Confirmed? |
| -------- | ------- | --------- | ---------- |
| `requirements.txt` | removed; `pyproject.toml` is the single source | User decision; README/Makefile/CI already use `pip install -e ".[…]"`. | y |
| Provider floors | first release of each package's LangChain-1.x line: anthropic/openai/groq/mistralai/ollama/deepseek/aws `>=1.0`, google-genai `>=3.0` | Each verified to resolve with `langchain-core==1.4.8` + `langchain==1.3.11` (`pip --dry-run`). | y (agent) |
| `all-providers` | same specs as the individual extras (now also includes `aws`? **no** — unchanged membership) | Avoids scope creep; consistency enforced by test. | y (agent) |

## Acceptance Criteria
1. **DEP-01** Every `langchain-*` provider requirement in `pyproject.toml` (core + extras + `all-providers`) SHALL have the floor above; none SHALL be pre-1.0 (google-genai pre-3.0).
2. **DEP-02** Each `all-providers` entry SHALL be identical to the corresponding individual extra.
3. **DEP-03** `requirements.txt` SHALL NOT exist, and no doc/Makefile/CI SHALL reference it as an install path.
4. **DEP-04** `pip install --dry-run -e ".[dev,api,all-providers,aws]"` SHALL resolve (verified, recorded).

## Traceability
| ID | Where | Status |
| -- | ----- | ------ |
| DEP-01..03 | `tests/test_ci_config.py` | Verified |
| DEP-04 | validation record | Verified |

## Execution notes
- Red phase: DEP-01 and DEP-03 failed; DEP-02 already held (kept as guard).
- DEP-04: `pip install --dry-run --ignore-installed -e ".[dev,api,all-providers,aws]"` → exit 0; resolves langchain 1.4.9, langchain-core 1.7.7, langgraph 1.2.20, anthropic 1.7.10, openai 1.7.4, google-genai 4.4.3, groq 1.1.3, mistralai 1.1.6, ollama 1.1.0, deepseek 1.1.1, aws 1.9.2.
- Floors verified individually with `pip --dry-run` against `langchain-core==1.4.8` + `langchain==1.3.11`; `langchain-anthropic==0.3.22` (old floor range) is NOT installable with them.
