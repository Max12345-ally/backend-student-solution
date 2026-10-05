.PHONY: check lint typecheck test

check: lint typecheck test

lint:
	python -m ruff check shop tests

typecheck:
	python -m mypy shop

test:
	python -m pytest
