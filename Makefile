.PHONY: install hooks test lint run clean

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

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache **/__pycache__ audit-reports
