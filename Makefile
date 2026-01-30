.PHONY:	setup test lint fmt

setup:
	python -m venv .venv && . ./.venv/bin/activate && pip install -e .[science, fastapi] -U pip

fmt:
	pre-commit run --all-files || true

lint:
	mypy src

test:
	pytest -q