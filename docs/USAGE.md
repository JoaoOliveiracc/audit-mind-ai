# Guia de Uso — Auditor-IA

## 1. Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"      # ou: pip install -r requirements.txt
```

Requer Python ≥ 3.10.

## 2. Configuração

Copie o exemplo e preencha a chave da Anthropic:

```bash
cp .env.example .env
```

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
AUDITOR_MODEL=claude-sonnet-4-5      # troque o modelo aqui, se quiser
AUDITOR_TEMPERATURE=0
AUDITOR_OUTPUT_DIR=./audit-reports
```

Variáveis disponíveis (todas opcionais exceto a chave):

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `AUDITOR_PROVIDER` | `anthropic` | Provedor de LLM (anthropic, openai, google_genai, groq, ollama, …). |
| `<PROVIDER>_API_KEY` | — | Credencial do provedor escolhido (ex.: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`). |
| `AUDITOR_MODEL` | `claude-sonnet-4-5` | Modelo usado (depende do provedor). |
| `AUDITOR_BASE_URL` | — | Endpoint customizado (Ollama, gateways compatíveis com OpenAI). |
| `AUDITOR_TEMPERATURE` | `0` | Temperatura de geração. |
| `AUDITOR_MAX_TOKENS` | `8000` | Máx. tokens de saída por chamada. |
| `AUDITOR_MAX_FILE_BYTES` | `200000` | Máx. bytes lidos por arquivo. |
| `AUDITOR_MAX_FILES` | `5000` | Máx. arquivos no inventário. |
| `AUDITOR_MAX_SEARCH_RESULTS` | `50` | Máx. resultados por busca. |
| `AUDITOR_MAX_INVESTIGATOR_STEPS` | `25` | Máx. passos de raciocínio por investigador. |
| `AUDITOR_OUTPUT_DIR` | `./audit-reports` | Diretório de saída dos relatórios. |

## 3. Executando uma auditoria

### Modo interativo (recomendado)

```bash
auditor audit /caminho/do/projeto --goal "Revisão pré-produção, foco em segurança e testes"
```

Fluxo no terminal:
1. O agent detecta a stack e mostra o progresso.
2. Faz perguntas de esclarecimento — responda ou pressione Enter para pular.
3. Executa os investigadores por dimensão (progresso ao vivo).
4. Consolida, pontua e grava os relatórios.
5. Exibe o resumo e os caminhos dos arquivos gerados.

### Modo não interativo (CI/automação)

```bash
auditor audit /caminho/do/projeto --no-questions
```

### Escolhendo o provedor de LLM

Instale o pacote do provedor e selecione-o por env ou flag:

```bash
pip install -e ".[openai]"          # ou .[google] / .[groq] / .[deepseek] / .[ollama] / .[all-providers]

auditor audit /proj --provider openai       --model gpt-4o
auditor audit /proj --provider google_genai --model gemini-2.0-flash
auditor audit /proj --provider deepseek     --model deepseek-chat
auditor audit /proj --provider ollama       --model qwen2.5-coder:14b   # local, sem chave

auditor providers                   # lista provedores, pacotes e credenciais
```

As flags `--provider`/`--model` sobrescrevem o `.env` apenas naquela execução.
Provedores como **Ollama** (local) e **Bedrock**/**Vertex AI** não usam
`*_API_KEY` — dependem, respectivamente, do serviço local e das credenciais da
nuvem (AWS/gcloud).

> **Compatibilidade:** o agent usa saída estruturada e tool-calling. Prefira
> modelos com bom suporte a *function calling* (a maioria dos modelos recentes
> de Anthropic/OpenAI/Google, e modelos locais como `qwen2.5-coder`).

### Saída

```
audit-reports/
├── auditoria-20260701-143022.md      # versionável, para o repositório
└── auditoria-20260701-143022.html    # auto-contido, para compartilhar
```

## 4. Interpretando o relatório

- **Pontuação de saúde (0–100):** heurística baseada nas severidades. ≥75 bom,
  50–74 atenção, <50 crítico.
- **Severidades:** `critical` > `high` > `medium` > `low` > `info`.
- **Confiança:** estimativa do agent (0–100%) sobre o achado. Achados de baixa
  confiança merecem verificação humana.
- **Evidência:** trecho real inspecionado pelo agent — sempre confira o arquivo/linha.

> O relatório é um **apoio à decisão**, não um veredito. Revise achados críticos manualmente.

## 5. Uso programático

```python
from auditor.graph import build_graph
from langgraph.types import Command

graph = build_graph()
config = {"configurable": {"thread_id": "minha-auditoria"}}

state = {"project_path": "/proj", "user_goal": "", "user_context": {},
         "findings": [], "dimension_summaries": []}

# roda até o interrupt de esclarecimento
result = graph.invoke(state, config)
if "__interrupt__" in result:
    perguntas = result["__interrupt__"][0].value["questions"]
    respostas = {q["question"]: "produção" for q in perguntas}
    result = graph.invoke(Command(resume=respostas), config)

final = graph.get_state(config).values
print(final["health_score"], final["report_html_path"])
```

## 6. Solução de problemas

| Sintoma | Causa provável | Solução |
| --- | --- | --- |
| `ANTHROPIC_API_KEY não configurada` | `.env` ausente/vazio | Preencha a chave. |
| `Recursion limit reached` | Projeto grande demais p/ os passos | Aumente `AUDITOR_MAX_INVESTIGATOR_STEPS`. |
| Auditoria lenta/cara | Muitas dimensões/arquivos | Reduza `AUDITOR_MAX_FILES` ou use `--goal` para focar. |
| Poucos achados | Contexto insuficiente | Responda às perguntas de esclarecimento com detalhes. |

## 7. Boas práticas de uso

- Rode a auditoria em uma cópia limpa do repositório (sem artefatos de build).
- Use `--goal` para direcionar o foco (ex.: "só segurança e dependências").
- Versione o `.md` no repositório para acompanhar a evolução ao longo do tempo.
- Trate a pontuação como tendência, não como nota absoluta.
