.PHONY: bootstrap dev-run test clean docker-build docker-run deploy-build deploy-push deploy-migrate deploy-start deploy-stop deploy-restart deploy-scale deploy-logs deploy-health deploy-clean

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

# Deployment targets
deploy-build:
	@echo "Building production Docker images..."
	docker-compose -f docker-compose.prod.yml build

deploy-push:
	@echo "Pushing images to registry..."
	@echo "Configure registry in docker-compose.prod.yml before pushing"
	@docker-compose -f docker-compose.prod.yml push || echo "Push failed - check registry configuration"

deploy-migrate:
	@echo "Running database migrations..."
	cd web && npx prisma migrate deploy && cd ..

deploy-start:
	@echo "Starting production services..."
	docker-compose -f docker-compose.prod.yml up -d

deploy-stop:
	@echo "Stopping production services..."
	docker-compose -f docker-compose.prod.yml down

deploy-restart:
	@echo "Restarting production services..."
	docker-compose -f docker-compose.prod.yml restart

deploy-scale:
	@echo "Scaling RQ workers..."
	@WORKERS=$${WORKERS:-2}; \
	docker-compose -f docker-compose.prod.yml up -d --scale rq-worker=$$WORKERS

deploy-logs:
	@echo "Viewing production logs..."
	docker-compose -f docker-compose.prod.yml logs -f

deploy-health:
	@echo "Checking service health..."
	@echo "FastAPI:" && curl -s http://localhost:8001/health/ready || echo "FastAPI not responding"
	@echo "Next.js:" && curl -s http://localhost:3000/api/health || echo "Next.js not responding"
	@echo "Container status:"
	@docker-compose -f docker-compose.prod.yml ps

deploy-clean:
	@echo "Cleaning up stopped containers..."
	docker-compose -f docker-compose.prod.yml down -v
	docker system prune -f

# Show help
help:
	@echo "Available targets:"
	@echo "  bootstrap       - Install dependencies"
	@echo "  dev-run         - Run the pipeline in development mode"
	@echo "  debug           - Run the pipeline in debug mode"
	@echo "  test            - Run tests"
	@echo "  clean           - Clean up"
	@echo "  docker-build    - Build Docker image (development)"
	@echo "  docker-run      - Run Docker containers (development)"
	@echo "  docker-stop     - Stop Docker containers (development)"
	@echo ""
	@echo "Deployment targets:"
	@echo "  deploy-build    - Build production Docker images"
	@echo "  deploy-push     - Push images to registry"
	@echo "  deploy-migrate  - Run database migrations"
	@echo "  deploy-start    - Start production services"
	@echo "  deploy-stop     - Stop production services"
	@echo "  deploy-restart  - Restart production services"
	@echo "  deploy-scale    - Scale worker services (WORKERS=N)"
	@echo "  deploy-logs     - View production logs"
	@echo "  deploy-health   - Check service health"
	@echo "  deploy-clean    - Clean up stopped containers"
	@echo "  help            - Show this help" 