"""
Makefile for backend API development.
"""

.PHONY: install dev run worker test lint format

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8001

worker:
	python -m app.workers.worker

test:
	pytest tests/

lint:
	ruff check app/

format:
	black app/
	ruff check --fix app/

