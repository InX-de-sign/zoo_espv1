.PHONY: help up down logs build clean restart test migrate setup

help:
	@echo "Available commands:"
	@echo "  make setup    - Initial setup (install deps, create dirs)"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make restart  - Restart all services"
	@echo "  make logs     - View logs (all services)"
	@echo "  make build    - Rebuild all containers"
	@echo "  make clean    - Clean up everything (volumes, cache)"
	@echo "  make test     - Run tests"
	@echo "  make migrate  - Run database migrations"

setup:
	@echo "Setting up Museum AI Companion..."
	chmod +x scripts/setup.sh
	./scripts/setup.sh

up:
	docker-compose up -d
	@echo "Services starting... Check status with 'make ps'"

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f --tail=100

logs-chatbot:
	docker-compose logs -f chatbot --tail=100

logs-cv:
	docker-compose logs -f cv-service --tail=100

ps:
	docker-compose ps

build:
	docker-compose build --no-cache

build-chatbot:
	docker-compose build --no-cache chatbot

clean:
	docker-compose down -v
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache

test:
	python -m pytest tests/ -v

test-chatbot:
	docker-compose run --rm chatbot python -m pytest tests/ -v

migrate:
	python scripts/migrate-db.py

backup:
	python scripts/backup.py

restore:
	python scripts/restore.py

# Development helpers
shell-chatbot:
	docker-compose exec chatbot /bin/bash

shell-postgres:
	docker-compose exec postgres psql -U museum_user -d museum_db

redis-cli:
	docker-compose exec redis redis-cli

# Health checks
health:
	@echo "Checking service health..."
	@curl -s http://localhost:8001/health | jq '.' || echo "Chatbot: Not responding"
	@curl -s http://localhost:8002/health | jq '.' || echo "CV Service: Not responding"
	@curl -s http://localhost:8003/health | jq '.' || echo "Localization: Not responding"