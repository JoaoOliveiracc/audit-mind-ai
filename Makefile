.PHONY: install test lint run clean

install:
	python3 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e ".[dev]"

test:
	. .venv/bin/activate && pytest -q

lint:
	. .venv/bin/activate && ruff check src tests

run:
	@# uso: make run PROJ=/caminho GOAL="foco"
	. .venv/bin/activate && auditor audit "$(PROJ)" $(if $(GOAL),--goal "$(GOAL)",)

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache **/__pycache__ audit-reports
