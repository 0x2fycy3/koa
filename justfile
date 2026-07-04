run:
    uv run python -m src.main

setup:
    uv sync

lint:
    uv run ruff check src/
