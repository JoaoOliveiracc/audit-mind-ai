.PHONY: install hooks test lint typecheck coverage ci frontend-ci run api frontend dev frontend-install clean

install: hooks
	python3 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e ".[dev,api]"

hooks:
	@# Ativa o hook de segurança versionado (bloqueia commit de .env e segredos).
	git config core.hooksPath .githooks && echo "hook de pre-commit ativado (.githooks)"

test:
	. .venv/bin/activate && pytest -q

lint:
	. .venv/bin/activate && ruff check src tests

typecheck:
	. .venv/bin/activate && mypy src

coverage:
	@# Cobertura do backend (só reporta; sem mínimo por enquanto — G39)
	. .venv/bin/activate && pytest -q --cov=auditor --cov-report=term-missing

frontend-ci:
	@# Mesmos passos do job "frontend" do CI (npm ci limpo + testes + tsc + build)
	cd frontend && npm ci --no-audit --no-fund && npm test && npm run build

ci: lint typecheck test frontend-ci
	@# Espelho local de .github/workflows/ci.yml — para no primeiro erro
	@echo "✓ make ci: todos os gates passaram"

run:
	@# uso: make run PROJ=/caminho GOAL="foco"
	. .venv/bin/activate && auditor audit "$(PROJ)" $(if $(GOAL),--goal "$(GOAL)",)

api:
	@# Sobe a API FastAPI em http://127.0.0.1:8020 (docs em /docs)
	. .venv/bin/activate && auditor serve --reload

frontend-install:
	cd frontend && npm ci

frontend:
	@# Frontend Vite/React em http://localhost:5173 (proxy da API -> :8020)
	cd frontend && npm run dev

dev:
	@# Sobe API + frontend juntos (Ctrl-C encerra ambos)
	$(MAKE) -j2 api frontend

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache **/__pycache__ audit-reports
