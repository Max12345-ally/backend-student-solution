.PHONY: check lint typecheck test

PYTHON ?= .venv/bin/python

check: lint typecheck test

lint:
	$(PYTHON) -m ruff check shop tests

typecheck:
	$(PYTHON) -m mypy shop

test:
	$(PYTHON) -m pytest
