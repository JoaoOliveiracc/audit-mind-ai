# Política de Segredos — Audit Mind AI

Este projeto lida com chaves de API de provedores de LLM. Regras e proteções para
evitar vazamento de credenciais.

## Regras

1. **Nunca** commite chaves reais. Valores reais vivem **apenas** no `.env`, que é
   ignorado pelo git (`.gitignore`).
2. O `.env.example` contém **somente placeholders** (ex.: `sk-ant-...`) e serve de modelo.
3. O `.env` deve ter permissão restrita ao dono: `chmod 600 .env`.
4. Se uma chave for exposta, **considere-a comprometida** e rotacione-a no console do provedor.

## Proteções automáticas

### `.gitignore`
Ignora `.env`, `.env.*` (exceto `.env.example`/`.sample`/`.template`), `*.pem`,
`*.key` e `secrets.*`.

### Hook de pre-commit (`.githooks/pre-commit`)
Bloqueia commits que:
- adicionem arquivos `.env` reais; ou
- contenham segredos com formato de chave real (Anthropic, OpenAI, Google, Groq,
  Slack, chaves privadas PEM) em **qualquer** arquivo versionado — inclusive o `.env.example`.

**Ative uma vez por clone** (o `core.hooksPath` é configuração local, não versionada):

```bash
make hooks           # ou:  git config core.hooksPath .githooks
```

Para pular intencionalmente (desaconselhado): `git commit --no-verify`.

## Se uma chave vazou para o histórico do git

1. Rotacione/revogue a chave imediatamente no provedor.
2. Remova do histórico:
   - commit único não enviado → `git commit --amend`;
   - múltiplos commits → `git filter-repo --replace-text` ou BFG.
3. Force-push apenas se necessário e com ciência da equipe.

## Rotação de chaves

| Provedor | Onde rotacionar |
| --- | --- |
| Anthropic | console.anthropic.com → API Keys |
| Google (Gemini) | Google AI Studio → API Keys |
| OpenAI | platform.openai.com → API Keys |
