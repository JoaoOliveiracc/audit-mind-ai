# Secrets Policy — Audit Mind AI

This project handles LLM provider API keys. Rules and protections to
prevent credential leakage.

## Rules

1. **Never** commit real keys. Real values live **only** in `.env`, which is
   ignored by git (`.gitignore`).
2. `.env.example` contains **only placeholders** (e.g., `sk-ant-...`) and serves as a template.
3. `.env` must have owner-restricted permissions: `chmod 600 .env`.
4. If a key is exposed, **consider it compromised** and rotate it in the provider console.

## Automatic protections

### `.gitignore`
Ignores `.env`, `.env.*` (except `.env.example`/`.sample`/`.template`), `*.pem`,
`*.key` and `secrets.*`.

### Pre-commit hook (`.githooks/pre-commit`)
Blocks commits that:
- add real `.env` files; or
- contain secrets in real-key format (Anthropic, OpenAI, Google, Groq,
  Slack, PEM private keys) in **any** versioned file — including `.env.example`.

**Enable it once per clone** (`core.hooksPath` is local, unversioned configuration):

```bash
make hooks           # or:  git config core.hooksPath .githooks
```

To intentionally skip (not recommended): `git commit --no-verify`.

## If a key leaked into git history

1. Rotate/revoke the key immediately at the provider.
2. Remove it from history:
   - single unpushed commit → `git commit --amend`;
   - multiple commits → `git filter-repo --replace-text` or BFG.
3. Force-push only if necessary and with the team's awareness.

## Threat model (audited code)

The project being audited is **untrusted input**:

- **Data egress:** file contents read by the investigators are sent to the configured LLM
  provider. For sensitive code, use a local provider (Ollama).
- **Prompt injection:** comments/strings in the audited repo can try to steer the agent
  (hide findings, invent findings, or push tool calls). Mitigations: tools are read-only and
  scoped to the project root; `verify` drops findings whose evidence is not on disk; the HTML
  report is autoescaped (no stored XSS). Findings can still be *suppressed* — treat the report
  as a decision aid.
- **Root scoping:** every tool resolves symlinks and rejects paths outside the root;
  `search_code` also rejects absolute globs and globs with a `..` component (G25/G26, fixed).
- **Local API:** binds to `127.0.0.1`, no authentication, CORS limited to the Vite dev origin.
  Requests whose `Host` is not loopback (`localhost`, `127.0.0.1`, `[::1]`) get `400` — this blocks
  DNS rebinding (G27). `auditor serve` refuses a non-local `--host` unless `--allow-remote` is given;
  even then, remote clients are only accepted for hosts listed in `AUDITOR_ALLOWED_HOSTS`.
- **Local data at rest:** `$AUDITOR_DATA_DIR/*.sqlite` (default `~/.config/auditor`) stores audit state, including excerpts of
  audited files. Nothing expires automatically: delete audits from the web history (or
  `DELETE /audits/{id}`), which removes metadata, checkpoints and the `.md/.html/.sarif` reports.
  `auditor db compact` reclaims space from legacy sub-agent checkpoints.

## Key rotation

| Provider | Where to rotate |
| --- | --- |
| Anthropic | console.anthropic.com → API Keys |
| Google (Gemini) | Google AI Studio → API Keys |
| OpenAI | platform.openai.com → API Keys |
