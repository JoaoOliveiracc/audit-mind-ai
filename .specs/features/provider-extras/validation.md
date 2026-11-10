# Validation — provider-extras (G47)

**Verdict: PASS** (independent Verifier, 2026-11-10)

## Gates
| Gate | Result |
| ---- | ------ |
| `.venv/bin/pytest -q` | 198 passed |
| `ruff check .` | All checks passed |

## Per-AC evidence
| AC | Evidence | Status |
| -- | -------- | ------ |
| PROV-01 | `test_prov01_every_advertised_provider_is_installable` passes; it kills mutants (a) and (e) | PASS |
| PROV-02 | pyproject has `vertexai>=3.0`, `cohere>=0.5`, `together>=0.4`, `fireworks>=1.0`; DEP-01 floor table extended; kills (b), (c); PyPI metadata below confirms the floors | PASS |
| PROV-03 | `pip install --dry-run --ignore-installed -e ".[vertexai,cohere,together,fireworks]"` gave exit 0 (re-run by Verifier) | PASS |
| PROV-04 | `test_prov04_readme_lists_new_extras` passes and kills (d) | PASS |

## Floor rule — PyPI `requires_dist` (langchain-core)
| Package | Release before the floor | Floor |
| ------- | ------------------------ | ----- |
| langchain-google-vertexai | 2.1.2: `>=0.3.76` (open-ended, 0.3 line) | 3.0.0: `>=1.0.0,<2.0.0` |
| langchain-cohere | 0.4.6: `>=0.3.76,<0.4.0` | 0.5.0: `>=1.0.0,<2.0` |
| langchain-together | 0.3.1: `>=0.3.29,<0.4.0` | 0.4.0: `>=1.2.22,<2` |
| langchain-fireworks | 0.3.0: `>=0.3.55,<1.0.0` | 1.0.0: `>=1.0.0,<2.0.0` |

Each floor is the first final release that declares core>=1.0. Pre-releases (vertexai 3.0.0rc1, fireworks 1.0.0a1) are left out, and `>=3.0` / `>=1.0` do not select them by default. Note: vertexai 2.1.2 does not exclude core 1.x, so the "declares" wording of the rule is what makes 3.0 the floor.

## Sensors (mutants, scratch copy under scratchpad/verifier20)
| Mutant | Result | Killed by |
| ------ | ------ | --------- |
| (a) remove `cohere` extra | 2 failed | DEP-01, PROV-01 |
| (b) vertexai floor 2.1 | 1 failed | DEP-01 |
| (c) fireworks floor 0.3 | 1 failed | DEP-01 |
| (d) remove `.[together]` from README | 1 failed | PROV-04 |
| (e) add `"xai": "langchain-xai"` to a copy of config.PROVIDER_PACKAGE (PYTHONPATH → copied src, import path checked) | 1 failed | PROV-01 |

5/5 killed, 0 survived. Baseline in the scratch copy: 18 passed.

## Docs coherence
README (`# or .[cohere], .[together], .[fireworks], .[aws]`), USAGE (`# or .[cohere] / ... / .[aws]`) and DOCUMENTACAO (`# ou .[cohere], ...`) all have the same install line `pip install -e ".[vertexai]"` with the same alternatives. DOCUMENTACAO marks G47 as resolved with the same floors, and its status header ("all done except G42") is consistent. The separators are slightly different (`,` vs `/`). This is cosmetic and does not block.
