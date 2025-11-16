.PHONY: install test lint format clean setup-repo

install:
	pip3 install -r requirements.txt
	pip3 install -e ".[dev]"
	pre-commit install

test:
	python3 test_server.py

lint:
	ruff check .
	black --check .
	mypy . --ignore-missing-imports || true

format:
	black .
	ruff check . --fix

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf build/ dist/ *.egg-info

setup-repo:
	bash scripts/setup-repo.sh

update-docs:
	bash scripts/update-docs.sh

