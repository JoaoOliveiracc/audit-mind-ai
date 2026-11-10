# Validation — dependency-floors (G40 remainder)

**Verdict: PASS** (independent Verifier; author != verifier)

## Gates
| Gate | Result |
| ---- | ------ |
| `.venv/bin/pytest -q` | 196 passed, 1 warning |
| `ruff check .` | All checks passed |

## Per-AC evidence
| AC | Evidence | Status |
| -- | -------- | ------ |
| DEP-01 | pyproject: core `langchain-anthropic>=1.0`; extras/all-providers openai/groq/mistralai/ollama/deepseek/aws `>=1.0`, google-genai `>=3.0`; no pre-1.0 floor left. Guard `test_dep01_*`. | PASS |
| DEP-02 | all-providers block matches each extra textually; guard `test_dep02_*` (mutant c killed). | PASS |
| DEP-03 | `requirements.txt` absent; grep over README/Makefile/docs/.github finds no reference (only historical mentions in DOCUMENTACAO.md). Guard `test_dep03_*`. | PASS |
| DEP-04 | `pip install --dry-run --ignore-installed -q -e ".[dev,api,all-providers,aws]"` → exit 0 (re-run by Verifier). | PASS |

## Dry-run spot checks (with `langchain-core==1.4.8 langchain==1.3.11`)
| Package | Exit |
| ------- | ---- |
| langchain-groq==1.0.0 | 0 (resolves) |
| langchain-google-genai==3.0.0 | 0 (resolves) |
| langchain-anthropic==0.3.22 | 1 (not installable — confirms the claim) |

## Sensor table (mutants on scratch copy, `pytest -q tests/test_ci_config.py`; baseline 16 passed)
| Mutant | Result |
| ------ | ------ |
| (a) openai extra floor -> 0.2 | KILLED (2 failed) |
| (b) google-genai floor -> 2.0 | KILLED (1 failed) |
| (c) groq `>=1.1` only in all-providers | KILLED (2 failed) |
| (d) recreate requirements.txt | KILLED (1 failed) |
| (e) README `pip install -r requirements.txt` | KILLED (1 failed) |
| (f) remove anthropic from core | KILLED (1 failed, set-equality check) |

## Judgment / advisories (non-blocking)
- Floor choice (first release of each package's LangChain-1.x line) is well justified: old floors were demonstrably uninstallable against core 1.4, and 1.0/3.0 were verified to resolve. A tighter floor is not needed since CI resolves latest.
- `config.PROVIDER_PACKAGE` also maps `google_vertexai`, `cohere`, `together`, `fireworks` (and `azure_openai` -> langchain-openai, covered by `openai`) without extras. Not a DEP-01 guard gap (spec scopes pyproject entries only), but a usability gap: no `pip install -e ".[cohere]"` path; users install the package manually with no floor. Consider adding extras or documenting it.
- DEP-03 guard matches the literal `-r requirements.txt` in 4 files only; other phrasings/files (e.g. CONTRIBUTING, DOCUMENTACAO) are not scanned. Acceptable.
