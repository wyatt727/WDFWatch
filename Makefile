.PHONY: bootstrap dev-run test clean docker-build docker-run

# Default target
all: bootstrap

# Bootstrap the project
bootstrap:
	@echo "Installing dependencies..."
	pip install poetry
	poetry install
	npm install -g @google/gemini-cli
	mkdir -p artefacts logs

# Run the pipeline in development mode
dev-run:
	@echo "Running pipeline in development mode..."
	python main.py

# Run the pipeline in debug mode
debug:
	@echo "Running pipeline in debug mode..."
	python main.py --debug

# Run tests
test:
	@echo "Running tests..."
	poetry run pytest -n auto

# Clean up
clean:
	@echo "Cleaning up..."
	rm -rf artefacts/*
	rm -rf logs/*
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Build Docker image
docker-build:
	@echo "Building Docker image..."
	docker-compose build

# Run Docker containers
docker-run:
	@echo "Starting Docker containers..."
	docker-compose up -d

# Stop Docker containers
docker-stop:
	@echo "Stopping Docker containers..."
	docker-compose down

# Show help
help:
	@echo "Available targets:"
	@echo "  bootstrap    - Install dependencies"
	@echo "  dev-run      - Run the pipeline in development mode"
	@echo "  debug        - Run the pipeline in debug mode"
	@echo "  test         - Run tests"
	@echo "  clean        - Clean up"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker containers"
	@echo "  docker-stop  - Stop Docker containers"
	@echo "  help         - Show this help" 