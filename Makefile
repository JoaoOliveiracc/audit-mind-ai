.PHONY: install hooks test lint run api frontend dev frontend-install clean

install: hooks
	python3 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e ".[dev]"

hooks:
	@# Ativa o hook de segurança versionado (bloqueia commit de .env e segredos).
	git config core.hooksPath .githooks && echo "hook de pre-commit ativado (.githooks)"

test:
	. .venv/bin/activate && pytest -q

lint:
	. .venv/bin/activate && ruff check src tests

run:
	@# uso: make run PROJ=/caminho GOAL="foco"
	. .venv/bin/activate && auditor audit "$(PROJ)" $(if $(GOAL),--goal "$(GOAL)",)

api:
	@# Sobe a API FastAPI em http://127.0.0.1:8020 (docs em /docs)
	. .venv/bin/activate && auditor serve --reload

frontend-install:
	cd frontend && npm install

frontend:
	@# Frontend Vite/React em http://localhost:5173 (proxy da API -> :8020)
	cd frontend && npm run dev

dev:
	@# Sobe API + frontend juntos (Ctrl-C encerra ambos)
	$(MAKE) -j2 api frontend

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache **/__pycache__ audit-reports
