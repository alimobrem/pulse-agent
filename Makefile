.PHONY: lint format type-check test verify helm-lint release

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

helm-lint:
	helm lint chart/
	helm template test chart/ --set vertexAI.projectId=test --set vertexAI.region=us-central1

release:
	@test -n "$(VERSION)" || (echo "Usage: make release VERSION=x.y.z" && exit 1)
	./scripts/bump-version.sh $(VERSION)
	git add pyproject.toml chart/Chart.yaml
	git commit -m "chore: bump version to $(VERSION)"
	git tag "v$(VERSION)"
	@echo "Release v$(VERSION) ready. Run 'git push && git push --tags' to trigger build."
