# API Hardening Validation

**Date**: 2026-11-10
**Spec**: `.specs/features/api-hardening/spec.md` (HOST-01..04, BIND-01..03, ORPH-01, RES-01..07, UI-01..03) · decisions AD-001/AD-002 (`.specs/STATE.md`)
**Diff range**: uncommitted working tree on `develop` (base `a37e81b`), limited to the files below
**Verifier**: independent sub-agent (author ≠ verifier); the real tree was not modified, and mutations ran only in a scratch copy

**Verdict: ❌ FAIL (minor).** All 18 ACs have evidence in the tests, and the behaviour that matters for security is well discriminated. The verdict is FAIL because four non-equivalent mutants survived (HOST-04 wiring, UI-01 "other statuses", UI-03 wiring, middleware order). There is also one latent race in a test.

---

## Diff surface

| File | Change |
| ---- | ------ |
| `src/auditor/api/security.py` (new) | `parse_host`, `allowed_hosts`, `LocalHostOnlyMiddleware` |
| `src/auditor/config.py:113` | `allowed_hosts` ← `AUDITOR_ALLOWED_HOSTS` |
| `src/auditor/api/main.py:19-33,48-52` | `lifespan` → `mark_orphans_interrupted`; Host middleware added last, so it is the outermost layer |
| `src/auditor/api/store.py:90` | `mark_orphans_interrupted()` |
| `src/auditor/api/runner.py:43-50,94-108` | `resume=True`, `_drive_resume()` |
| `src/auditor/api/routes.py:128-150` | `POST /audits/{id}/resume` |
| `src/auditor/cli.py:227-253` | `serve --allow-remote`, bind guard |
| `tests/test_security.py` (new), `tests/test_lifecycle.py` (new), `tests/test_api.py:9,178-252`, `tests/test_cli.py:73-104` | tests |
| `frontend/src/components/History.tsx`, `History.test.tsx:66-92`, `src/api/client.ts:58-61`, `src/App.tsx:120-134,195-197` | UI |

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1–T5 | ✅ Done | Code and tests are present |
| T6 | ⚠️ Done, weak | UI-03 has no behavioural test (the matrix allows "none", but see the sensor results) |
| T7 | ✅ Done | Docs are modified (not reviewed in depth) |

---

## Spec-Anchored Acceptance Criteria

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| HOST-01 | loopback ± port, any case → served | `tests/test_security.py:19-24`, parametrized `localhost`, `localhost:8020`, `127.0.0.1:8020`, `[::1]`, `[::1]:8020`, `LOCALHOST:5173` — `r.status_code == 200`, `r.json()["status"] == "ok"` | ✅ PASS (bare `127.0.0.1` without a port is not in the list; covered implicitly) |
| HOST-02 | other host → `400`, body `Host não permitido.`, route not run | `tests/test_security.py:28-33` — `status_code == 400` and `r.text == "Host não permitido."`; `:36-47` — `calls == []` (spy `create` never called) | ✅ PASS |
| HOST-03 | missing/empty Host → `400` | `tests/test_security.py:51-53` — `headers={"host": ""}` → `status_code == 400` | ✅ PASS (only the empty header is tested; a truly absent header is not, but it takes the same `get("host","")` path) |
| HOST-04 | `AUDITOR_ALLOWED_HOSTS="a.local, B.local"` → a/b allowed + defaults | `tests/test_security.py:57-69` — `a.local:8020`/`b.local`/`localhost` → 200, `c.local` → 400 | ⚠️ PASS on a mini-app only. The wiring in `main.py:51` is untested (mutant d2 survived) |
| BIND-01 | `127.0.0.1`/`localhost`/`::1` → starts | `tests/test_cli.py:85-88` — `exit_code == 0`, `started[0]["host"] == host` | ✅ PASS |
| BIND-02 | other host, no flag → exit `2`, message with `--allow-remote`, no start | `tests/test_cli.py:92-96` — `exit_code == 2`, `"--allow-remote" in output`, `started == []` | ✅ PASS |
| BIND-03 | flag → warning (no auth + `AUDITOR_ALLOWED_HOSTS`), starts | `tests/test_cli.py:99-104` — `"sem autenticação"`, `"AUDITOR_ALLOWED_HOSTS"` in output, `started[0]["host"] == "0.0.0.0"` | ✅ PASS |
| ORPH-01 | started/running/waiting_input → interrupted; completed/error unchanged | `tests/test_lifecycle.py:21-30` — `changed == 3` + a full status map; `:34-43` lifespan via `with TestClient` (store monkeypatched) | ✅ PASS |
| RES-01 | pending interrupt → `clarification` with the same questions, `waiting_input`, answers → `completed` | `tests/test_lifecycle.py:111-129` — `questions == QUESTIONS`, `last("status") == "waiting_input"`, then `"completed"`, `answers` persisted | ✅ PASS (latent race, see gap 5) |
| RES-02 | pending nodes, no interrupt → `stream(None)` → `completed` | `tests/test_lifecycle.py:132-147` — `runs == ["finish"]`, `completed`, `health_score == 80`, no clarification | ✅ PASS |
| RES-03 | nothing pending → `completed` + paths/score from state, no nodes run | `tests/test_lifecycle.py:150-168` — `runs == []`, no `phase`, `report_html`/`report_sarif`/`health_score` | ✅ PASS (`report_md` not asserted) |
| RES-04 | interrupted → `200`, summary `running`, stream available | `tests/test_api.py:208-216` — `200`, `json()["status"] == "running"`, store `running`, runner args `(…, None, True)`, `registry["int"] is started[0]` | ✅ PASS (stream availability is shown through the registry, not through `/stream`) |
| RES-05 | unknown id → `404` | `tests/test_api.py:219-220` — `status_code == 404` | ✅ PASS, but weak; see the discrimination note |
| RES-06 | `completed`/`error`/live runner → `409` | `tests/test_api.py:223-227` (`done`, `err`) and `:230-238` (live) — `== 409`, `started == []` | ✅ PASS |
| RES-07 | `LLMConfigError` → `400`, status stays `interrupted` | `tests/test_api.py:241-252` — `400`, detail text, store `interrupted`, `started == []` | ✅ PASS |
| UI-01 | interrupted → `interrompida` + `Retomar`; other statuses → no button | `frontend/src/components/History.test.tsx:73-80` — `getByText('interrompida')`, `getAllByRole(... /^Retomar/)` length 1 | ⚠️ PASS. "Other statuses" is tested only with `completed` (mutant n2 survived) |
| UI-02 | click → `onResume(audit)`, not `onOpen` | `History.test.tsx:82-91` — `onResume` called once with `interrupted`, `onOpen`/`onDelete` not called | ✅ PASS |
| UI-03 | success → live run view on the stream; failure → API error shown | **no test**; tsc only (`App.tsx:120-134`) | ❌ GAP. No `file:line` assertion. The no-stream mutant survived tsc and vitest |

**Status**: 15 of 18 fully matched, 2 partial (HOST-04 wiring, UI-01 breadth), 1 uncovered (UI-03).

**RES-05 discrimination**: before the route existed, the test passed only because FastAPI returns 404 for an unknown path. With the route in place it does discriminate: mutant t (the 404 guard removed) fails with a `TypeError` and HTTP 500. It still cannot tell "route missing" from "route says 404". Asserting `detail == "Auditoria não encontrada."` would make it discriminate on its own.

---

## Discrimination Sensor

Scratch copy: `/tmp/claude-1000/-home-joao-Documentos-auditor-IA/3a865784-2fa5-4436-aa9a-ec628bd6b1d6/scratchpad/verifier4/`. I confirmed that `auditor.__file__` resolves to the copy (pytest `pythonpath=["src"]`). The frontend copy uses a symlink to `node_modules`. The driver script is `/tmp/claude-1000/-home-joao-Documentos-auditor-IA/3a865784-2fa5-4436-aa9a-ec628bd6b1d6/scratchpad/mut.py`.

| # | File:line | Mutation | Result |
| - | --------- | -------- | ------ |
| a | `security.py:22-25` | `parse_host` → `value.split(":")[0]` | ✅ Killed (`[::1]`) |
| b | `security.py:21` | drop `.lower()` | ✅ Killed (`LOCALHOST:5173`) |
| c | `security.py:42` | pass through when Host empty | ✅ Killed (HOST-03) |
| d | `security.py:31` | extras ignored in `allowed_hosts` | ✅ Killed (HOST-04) |
| d2 | `main.py:51` | wiring uses `allowed_hosts("")` (setting ignored) | ❌ **Survived** |
| e | `main.py:38-52` | Host middleware added before CORS | ❌ **Survived**. Preflight with `Host: evil` + `Origin: http://localhost:5173` → `200 OK` instead of `400 Host não permitido.` (breaks HOST-02 as written). Not exploitable: a rebinding origin is `evil.*`, so CORS rejects it anyway |
| u | `security.py:40` | websocket scope not checked | ⚪ Survived. No websocket routes exist, so this is a defensive branch; acceptable |
| f | `cli.py:243` | guard `host != "127.0.0.1"` | ✅ Killed (`localhost`) |
| g | `cli.py:250` | no warning with `--allow-remote` | ✅ Killed |
| h | `store.py:94` | also mark `error` | ✅ Killed |
| h2 | `store.py:94` | skip `started` | ✅ Killed |
| i | `main.py:33` | lifespan not wired | ✅ Killed |
| j | `runner.py:108` | resume always `_drive(None)` | ⚪ Survived, **equivalent**. LangGraph re-runs the interrupted node, which calls `interrupt()` again with the same questions from state. `clarify_node` is LLM-free (questions come from `plan_questions_node`), so production behaviour is the same |
| j2 | `runner.py:101` | re-asked questions emptied | ✅ Killed |
| k | `routes.py:138` | allow `error` | ✅ Killed |
| l | `routes.py:141` | skip LLM validation | ✅ Killed |
| m | `routes.py:145` | no `status="running"` | ✅ Killed |
| p | `routes.py:147` | runner not put in registry | ✅ Killed |
| q | `routes.py:136` | live-runner check removed | ✅ Killed |
| r | `routes.py:146` | `resume=False` | ✅ Killed |
| t | `routes.py:132-133` | 404 guard removed | ✅ Killed (500) |
| n | `History.tsx:58` | `Retomar` shown for every status | ✅ Killed |
| n2 | `History.tsx:58` | `Retomar` also shown for `error` | ❌ **Survived** |
| o | `History.tsx:64` | click also calls `onOpen` | ✅ Killed |
| — | `History.tsx:9` | `interrompida` label removed | ✅ Killed |
| UI3 | `App.tsx:128` | `openStream(a.id)` removed on resume | ❌ **Survived** (vitest 18/18 and tsc pass) |
| race | `runner.py:110` | 100 ms delay before `waiting_input` update | ❌ RES-01 test fails, which exposes a latent ordering assumption (150 normal runs passed) |

**Sensor depth**: expanded (P0: security and data integrity), 26 mutants.
**Result**: 20 killed, 6 survived. Of the survivors, 2 are equivalent or acceptable (j, u) and 4 are real (d2, e, n2, UI3). **FAIL**

---

## Security review (middleware and resume)

- **Absolute-form request target** (`GET http://localhost/... HTTP/1.1` with `Host: evil`): the middleware checks only the `Host` header, so this is rejected. Browsers never send absolute-form to an origin server, so it is not a rebinding vector. ✅
- **`X-Forwarded-Host`**: ignored, which is correct. Uvicorn's proxy-headers handling does not rewrite `Host`. ✅
- **Duplicate `Host`**: `Headers.get` uses the first value. `[localhost, evil]` reaches the app and `[evil, localhost]` gets 400 (I probed this directly). Browsers cannot send duplicate Host headers. Low risk, theoretical, for non-browser clients only.
- **Parser leniency**: `[::1]evil.example` → `[::1]` and `localhost:evil` → `localhost`, so both are *allowed*. A browser cannot produce either, because they are not valid URL hosts. Low risk. Trailing dot (`localhost.`), `127.1`, and `[::ffff:127.0.0.1]` are rejected, which fails safe.
- **WebSocket scope**: checked. The `PlainTextResponse` on a ws scope is invalid ASGI but still refuses the connection (same as Starlette `TrustedHostMiddleware`). There are no ws routes. ✅
- **Middleware order**: correct (outermost). The comment's claim "inclusive preflight CORS" is true but untested (mutant e).
- **Resume vs concurrent DELETE (audit-retention)**: TOCTOU. Both are sync routes in the threadpool. If DELETE runs its registry check (no runner yet) while resume is in `get_llm`, resume then registers and starts a runner while DELETE removes the checkpoints and the row, then `registry.pop`s the *live* runner. Resume's final `_summary(store.get(id))` can then get `None`, which gives a 500. The window is narrow and the user is local, so the risk is low, but it exists.
- **Double resume (double-click `Retomar`)**: TOCTOU. The window spans `get_llm()`, which is slow (it imports the provider package and builds a client). Two requests can both pass the `interrupted` and registry checks, and that starts **two runners on the same `thread_id`**. The second overwrites the registry entry. The button is not disabled while the request is in flight. **Medium risk.** RES-06 ("live runner → 409") only holds sequentially.

## Real home directory

- The gate run left `~/.config/auditor/audits.sqlite*` mtimes and sizes unchanged (stat diff before and after).
- The lifespan fires only in `tests/test_lifecycle.py:38`, with `api_main.get_store` monkeypatched to a tmp store. No other `with TestClient(...)` exists, and the module-level `client` in `test_api.py` does not run the lifespan. ✅
- Pre-existing tests (not part of this feature), such as `test_api.py:33` `test_get_missing_audit_404` and `test_create_audit_invalid_path`, open the real `AuditStore()` through `routes.get_store()` for reads. They do not write.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical / no scope creep | ✅ |
| Matches patterns | ✅ (the mid-file imports with `# noqa: E402` in `test_lifecycle.py:47-53` and `test_api.py:179` are a style smell) |
| Spec-anchored outcome check | ⚠️ HOST-04 (wiring), UI-01 (breadth), UI-03 (none) |
| Per-layer coverage (routes happy + every status path) | ✅ 200/400/404/409 all present |
| Every test maps to an AC | ✅ (tests tagged with spec IDs) |
| Guidelines | none (strong defaults applied) |

## Edge Cases

- [x] IPv6 with port (HOST-01)
- [x] Port on a rejected host (HOST-02)
- [x] Empty Host (HOST-03). A truly absent header is untested but takes the same code path.
- [x] Live runner on resume (RES-06), sequential only. The concurrent case is unprotected (see the security review).

## Gate Check

- **Backend**: `.venv/bin/pytest -q` → **90 passed**, 0 failed, 0 skipped. `ruff check src tests` → clean.
- **Frontend**: `vitest run` → **18 passed** (3 files). `tsc --noEmit -p .` → clean.
- **New tests in this feature**: 32 backend (security 14, lifecycle 5, api 6, cli 7) and 2 frontend. No tests were removed and no assertions were weakened. The only change to an existing test is the `base_url` on `test_api.py:9`, which the spec documents.

---

## Fix Plans

1. ✅ RESOLVED (fix loop 1): d2 killed by `test_real_app_reads_allowed_hosts_from_env`. **HOST-04 wiring (Major)**: add a test that sets `AUDITOR_ALLOWED_HOSTS`, clears the `get_settings` cache, reloads or rebuilds `auditor.api.main.app`, and asserts that `Host: a.local` → 200 on the real app. It should kill d2.
2. ✅ RESOLVED (fix loop 1): n2 killed. **UI-01 breadth (Minor)**: render `started`/`running`/`waiting_input`/`completed`/`error` together with `interrupted`, and assert exactly one `Retomar`. It should kill n2.
3. ✅ RESOLVED (fix loop 1): UI3 killed by `App.test.tsx`. **UI-03 (Minor)**: add an App-level Vitest with `resumeAudit` and `connectAuditStream` mocked. On success, assert the stream opens for the id and the run view renders. On rejection, assert the error text renders. It should kill UI3.
4. ✅ RESOLVED backend (fix loop 1): `_lifecycle_lock` plus a re-check inside it; x1 killed. Residual: `Retomar` is still not disabled while in flight (cosmetic, since the backend returns 409), and the delete-side lock is untested (x2). **Double-resume / DELETE race (Major, design)**: make check-and-register atomic. For example, put a lock or a placeholder in `registry`, or do a compare-and-set `UPDATE … SET status='running' WHERE id=? AND status='interrupted'` and check `rowcount`, before `get_llm`/start. Disable `Retomar` while the request is in flight. Add a test with two concurrent POSTs → one 200 and one 409.
5. ✅ RESOLVED (fix loop 1). **RES-01 test race (Minor)**: change `test_lifecycle.py:123` to `_wait(lambda: store.updates and store.last("status") == "waiting_input")`.
6. ✅ RESOLVED (fix loop 1): e killed. **Preflight / HOST-02 (Minor)**: add an `OPTIONS` test with `Host: evil` + `Origin: http://localhost:5173` → 400 `Host não permitido.` It should kill e.
7. ✅ RESOLVED (fix loop 1): `detail` asserted and strict `_HOST_RE` added; x4 and x5 killed. Optional: in the RES-05 test, assert `detail == "Auditoria não encontrada."`. Consider strict `parse_host`, which would reject trailing garbage after `]` or a non-numeric port.

## Requirement Traceability Update

| Requirement | New Status |
| ----------- | ---------- |
| HOST-01..03, BIND-01..03, ORPH-01, RES-01..07, UI-02 | ✅ Verified |
| HOST-04 | ⚠️ Needs test (wiring) |
| UI-01 | ⚠️ Needs test (other statuses) |
| UI-03 | ❌ Needs test |

## Summary

**Overall**: ⚠️ Issues. The core security behaviour is solid and the remaining gaps are test-discrimination and concurrency.
**Spec-anchored check**: 15/18 matched, 2 partial, 1 uncovered. **Sensor**: 20/26 killed (2 survivors equivalent or acceptable). **Gate**: 90 + 18 passed, ruff and tsc clean.

---

## Re-verification (fix loop 1)

**Verifier**: fresh and independent (verifier5). It ran against the working tree on 2026-11-10. Mutants were applied only to a scratch copy (`scratchpad/verifier5`). The copy's `src` was confirmed to be the one imported (`auditor.__file__` resolves to the copy). `PYTHONPATH` pointed at the copy, so the subprocess wiring test also imported the mutated code.

### Gates (real repo)

- `.venv/bin/pytest -q` → **101 passed**, 0 failed.
- `ruff check src tests` → clean.
- `vitest run` → **25 passed** (4 files).
- `tsc --noEmit -p .` → clean.

### Mutants

| ID | Mutation | Result | Killed by |
| -- | -------- | ------ | --------- |
| d2 | `main.py` builds allowlist without the setting (`allowed_hosts()`) | ✅ Killed | `test_real_app_reads_allowed_hosts_from_env` |
| e | Host middleware added before CORS (CORS outermost) | ✅ Killed | `test_cors_preflight_with_foreign_host_is_rejected` |
| n2 | `Retomar` also shown for `error` | ✅ Killed | `History.test.tsx` "status error não mostra Retomar" |
| UI3 | `openStream(a.id)` removed from `handleResumeAudit` | ✅ Killed | `App.test.tsx` "sucesso: conecta ao stream…" |
| x1 | re-check of status/registry inside `_lifecycle_lock` removed | ✅ Killed | `test_concurrent_double_resume_starts_only_one_runner` |
| x2 | `_lifecycle_lock` removed from `DELETE /audits/{id}` | ❌ Survived | n/a |
| x3 | `allowed_hosts` keeps `""` from invalid extras | ✅ Killed | `test_empty_host_is_rejected` |
| x4 | duplicate `Host` accepted (first value used) | ✅ Killed | `test_duplicate_host_headers_are_rejected` |
| x5 | `_HOST_RE` port part `(?::.*)?` | ✅ Killed | `test_malformed_hosts_are_rejected[localhost:evil]` |

**Result**: 8 of 9 killed.

**About x2**: the tests cannot detect this mutant, and that is structural. `test_delete_during_resume_validation_does_not_500` blocks resume inside `get_llm`, which is *outside* the lock. DELETE then runs to completion before resume ever takes the lock, and the re-check inside the lock returns 404. That holds with or without the delete-side lock. The delete-side lock matters only when DELETE lands in the short window *inside* resume's critical section (`store.update` → `registry[...] = runner`). Without it, DELETE can see no runner, delete the row, and leave resume to start a runner on a deleted audit, which gives a 500 from `_summary(None)`.

A deterministic test would need resume blocked inside the lock (for example, a blocking `get_graph`), plus proof that DELETE did not enter `delete_audit` while it was held. That proof is a bounded negative wait, which is timing-based. Judgement: **acceptable**. It is the same lock object, the change is a one-line `with`, it is verified by review, and the residual window is microseconds with a local, single user. It is recorded as a non-blocking residual.

### Determinism of the race tests

Both race tests synchronise on `threading.Event` (`entered` and `release`), with bounded waits (`wait(5)`, `join(5)`). Neither uses sleeps for synchronisation. The 20 ms sleep in `test_lifecycle._wait` is a bounded poll interval, not a sync point.

- `test_concurrent_double_resume_starts_only_one_runner`: **30/30** passed.
- `test_delete_during_resume_validation_does_not_500`: **30/30** passed.
- `tests/test_lifecycle.py` (gap 5): 10/10 passed.

`pytest-repeat` is not installed, so these runs used a shell loop.

### Per-gap status

| Gap | Status |
| --- | ------ |
| 1 Double resume / resume×delete race | ✅ Resolved. The lock plus the re-check is correct, and x1 is killed. The delete-side lock is covered by review only (x2, accepted). |
| 2 HOST-04 wiring | ✅ Resolved (d2 killed). Note that the subprocess resolves `auditor` through the venv's editable install, which points at the repo `src`. |
| 3 UI-03 untested | ✅ Resolved (UI3 killed). Both success and error paths are covered. |
| 4 UI-01 breadth | ✅ Resolved (`it.each` over 5 statuses, n2 killed). |
| 5 RES-01 flake | ✅ Resolved (waits for `waiting_input`, 10/10 passed). |
| 6 Middleware order | ✅ Resolved (e killed). |
| 7 RES-05 weak | ✅ Resolved (`detail` asserted). |
| Hardening (strict Host, duplicates, empty extras) | ✅ x3, x4 and x5 killed. The earlier parser-leniency and duplicate-Host findings in the security review are now closed. |

**Non-blocking residuals:**

- (a) x2 above.
- (b) `Retomar` is not disabled while the request is in flight. With a double click, the second request gets a 409, and its error text and history refresh can appear alongside the started run. This is cosmetic, and the backend is safe.

### Requirement Traceability (updated)

HOST-01..04, BIND-01..03, ORPH-01, RES-01..07 and UI-01..03 are all ✅ Verified.

### Verdict: **PASS**
