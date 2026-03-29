.PHONY: lint format type-check test verify

lint:
	ruff check sre_agent/ tests/

format:
	ruff format sre_agent/ tests/

type-check:
	mypy sre_agent/ --ignore-missing-imports

test:
	python -m pytest tests/ -q

verify: lint type-check test
	@echo "All checks passed."
