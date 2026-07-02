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

## Key rotation

| Provider | Where to rotate |
| --- | --- |
| Anthropic | console.anthropic.com → API Keys |
| Google (Gemini) | Google AI Studio → API Keys |
| OpenAI | platform.openai.com → API Keys |
