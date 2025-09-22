# Auto WordPress Post Generator - Development Makefile

.PHONY: help build up down logs shell db-shell test lint format clean

# Default target
help:
	@echo "Available commands:"
	@echo "  build     - Build Docker images"
	@echo "  up        - Start all services"
	@echo "  down      - Stop all services"
	@echo "  logs      - View service logs"
	@echo "  shell     - Open shell in API container"
	@echo "  db-shell  - Open PostgreSQL shell"
	@echo "  migrate   - Run database migrations"
	@echo "  test      - Run tests"
	@echo "  lint      - Run linting"
	@echo "  format    - Format code"
	@echo "  clean     - Clean up containers and volumes"

# Docker operations
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

# Development tools
shell:
	docker-compose exec api bash

db-shell:
	docker-compose exec db psql -U postgres -d writer

migrate:
	docker-compose exec api alembic upgrade head

migrate-create:
	docker-compose exec api alembic revision --autogenerate -m "$(MESSAGE)"

# Testing and code quality
test:
	docker-compose exec api pytest

test-coverage:
	docker-compose exec api pytest --cov=app --cov-report=html

lint:
	docker-compose exec api flake8 app/
	docker-compose exec api mypy app/

format:
	docker-compose exec api black app/
	docker-compose exec api isort app/

# Cleanup
clean:
	docker-compose down -v
	docker system prune -f

# Setup for development
setup: build up migrate
	@echo "Development environment is ready!"
	@echo "API available at: http://localhost:8080"
	@echo "API docs at: http://localhost:8080/docs"

# Reset everything
reset: clean setup