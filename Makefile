# =============================================================================
# CampusHub Makefile
# Convenience commands for development and deployment
# =============================================================================

# Colors
GREEN = \033[0;32m
YELLOW = \033[0;33m
BLUE = \033[0;34m
NC = \033[0m # No Color
PYTHON ?= python

# Help
help:
	@echo ""
	@echo "${BLUE}CampusHub Makefile${NC}"
	@echo ""
	@echo "${GREEN}Development:${NC}"
	@echo "  make up          - Start all services (development)"
	@echo "  make down        - Stop all services"
	@echo "  make logs        - View logs"
	@echo "  make shell      - Open Django shell"
	@echo "  make migrate    - Run migrations"
	@echo "  make makemigrations - Create migrations"
	@echo ""
	@echo "${GREEN}Production:${NC}"
	@echo "  make prod-up    - Start production services"
	@echo "  make prod-down  - Stop production services"
	@echo "  make prod-readiness - Run production readiness command"
	@echo "  make prod-verify - Run production backend readiness checks"
	@echo "  make prod-compose-validate - Validate production compose config"
	@echo "  make ensure-admin - Create/update admin user from env vars"
	@echo "  make build      - Build Docker images"
	@echo "  make rebuild    - Rebuild containers"
	@echo ""
	@echo "${GREEN}Testing:${NC}"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linters"
	@echo "  make mobile-test - Run mobile backend test suite"
	@echo "  make mobile-screen-smoke - Compile all mobile screens/routes"
	@echo "  make mobile-contract - Export mobile OpenAPI contract"
	@echo "  make mobile-infra-check - Run mobile infra dependency checks"
	@echo "  make mobile-verify - Run mobile backend readiness checks"
	@echo ""
	@echo "${GREEN}Database:${NC}"
	@echo "  make db-backup  - Backup database"
	@echo "  make db-restore - Restore database"
	@echo ""
	@echo "${GREEN}Cleanup:${NC}"
	@echo "  make clean      - Remove containers and volumes"
	@echo "  make prune      - Clean up unused Docker resources"

# Development
up:
	@echo "${GREEN}Starting development services...${NC}"
	docker-compose up -d
	@echo "${GREEN}Services started!${NC}"
	@echo "Web: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/api/docs/"
	@echo "Admin: http://localhost:8000/admin/"

down:
	@echo "${YELLOW}Stopping services...${NC}"
	docker-compose down

logs:
	docker-compose logs -f

logs-web:
	docker-compose logs -f web

shell:
	docker-compose exec web python manage.py shell

migrate:
	docker-compose exec web python manage.py migrate

makemigrations:
	docker-compose exec web python manage.py makemigrations

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput

# Production
prod-up:
	@echo "${GREEN}Starting production services...${NC}"
	docker-compose -f docker-compose.prod.yml up -d
	@echo "${GREEN}Production services started!${NC}"

prod-down:
	@echo "${YELLOW}Stopping production services...${NC}"
	docker-compose -f docker-compose.prod.yml down

prod-verify:
	@echo "${BLUE}Running production backend readiness checks...${NC}"
	ENVIRONMENT=production \
	SECRET_KEY='campushub-prod-check-secret-key-very-strong-1234567890ABCD' \
	ALLOWED_HOSTS='api.campushub.local,campushub.local' \
	CSRF_TRUSTED_ORIGINS='https://api.campushub.local,https://campushub.local' \
	DATABASE_URL='sqlite:////tmp/campushub_prod_check.sqlite3' \
	$(PYTHON) manage.py check --deploy
	ENVIRONMENT=production \
	SECRET_KEY='campushub-prod-check-secret-key-very-strong-1234567890ABCD' \
	ALLOWED_HOSTS='api.campushub.local,campushub.local' \
	CSRF_TRUSTED_ORIGINS='https://api.campushub.local,https://campushub.local' \
	DATABASE_URL='sqlite:////tmp/campushub_prod_check.sqlite3' \
	$(PYTHON) manage.py migrate --noinput
	ENVIRONMENT=production \
	SECRET_KEY='campushub-prod-check-secret-key-very-strong-1234567890ABCD' \
	ALLOWED_HOSTS='api.campushub.local,campushub.local' \
	CSRF_TRUSTED_ORIGINS='https://api.campushub.local,https://campushub.local' \
	DATABASE_URL='sqlite:////tmp/campushub_prod_check.sqlite3' \
	$(PYTHON) manage.py production_readiness_check --allow-sqlite
	ENVIRONMENT=production \
	SECRET_KEY='campushub-prod-check-secret-key-very-strong-1234567890ABCD' \
	ALLOWED_HOSTS='api.campushub.local,campushub.local' \
	CSRF_TRUSTED_ORIGINS='https://api.campushub.local,https://campushub.local' \
	DATABASE_URL='sqlite:////tmp/campushub_prod_check.sqlite3' \
	$(PYTHON) manage.py migrate --check
	ENVIRONMENT=production \
	SECRET_KEY='campushub-prod-check-secret-key-very-strong-1234567890ABCD' \
	ALLOWED_HOSTS='api.campushub.local,campushub.local' \
	CSRF_TRUSTED_ORIGINS='https://api.campushub.local,https://campushub.local' \
	DATABASE_URL='sqlite:////tmp/campushub_prod_check.sqlite3' \
	$(PYTHON) manage.py spectacular --validate --file /tmp/openapi_prod.yaml
	ENVIRONMENT=production \
	SECRET_KEY='campushub-prod-check-secret-key-very-strong-1234567890ABCD' \
	ALLOWED_HOSTS='api.campushub.local,campushub.local' \
	CSRF_TRUSTED_ORIGINS='https://api.campushub.local,https://campushub.local' \
	DATABASE_URL='sqlite:////tmp/campushub_prod_check.sqlite3' \
	$(PYTHON) manage.py collectstatic --noinput --dry-run
	@echo "${GREEN}Production backend readiness checks passed.${NC}"

prod-readiness:
	@echo "${BLUE}Running production_readiness_check...${NC}"
	ENVIRONMENT=production \
	SECRET_KEY='campushub-prod-check-secret-key-very-strong-1234567890ABCD' \
	ALLOWED_HOSTS='api.campushub.local,campushub.local' \
	CSRF_TRUSTED_ORIGINS='https://api.campushub.local,https://campushub.local' \
	DATABASE_URL='sqlite:////tmp/campushub_prod_check.sqlite3' \
	$(PYTHON) manage.py migrate --noinput
	ENVIRONMENT=production \
	SECRET_KEY='campushub-prod-check-secret-key-very-strong-1234567890ABCD' \
	ALLOWED_HOSTS='api.campushub.local,campushub.local' \
	CSRF_TRUSTED_ORIGINS='https://api.campushub.local,https://campushub.local' \
	DATABASE_URL='sqlite:////tmp/campushub_prod_check.sqlite3' \
	$(PYTHON) manage.py production_readiness_check --allow-sqlite
	@echo "${GREEN}Production readiness command passed.${NC}"

prod-compose-validate:
	@echo "${BLUE}Validating production docker compose config...${NC}"
	docker compose -f docker-compose.prod.yml config >/tmp/docker-prod-config.txt
	@echo "${GREEN}Compose config is valid.${NC}"

ensure-admin:
	@echo "${BLUE}Ensuring admin account exists...${NC}"
	$(PYTHON) manage.py ensure_superuser
	@echo "${GREEN}Admin ensure command completed.${NC}"

build:
	docker-compose build

rebuild:
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d

# Testing
test:
	docker-compose exec web pytest

lint:
	docker-compose exec web flake8 apps
	docker-compose exec web black --check apps
	docker-compose exec web isort --check-only apps

mobile-test:
	$(PYTHON) -m pytest -q tests/api/test_mobile_endpoints_extended.py tests/api/test_mobile_readiness.py tests/api/test_mobile_backend_hardening.py tests/api/test_mobile_feature_endpoints.py tests/core/test_mobile_infra_check.py

mobile-screen-smoke:
	cd mobile && npm run test:screens

mobile-contract:
	mkdir -p docs/openapi
	$(PYTHON) manage.py spectacular --validate --file docs/openapi/mobile-v1.yaml
	@echo "${GREEN}Mobile OpenAPI contract exported: docs/openapi/mobile-v1.yaml${NC}"

mobile-infra-check:
	$(PYTHON) manage.py mobile_infra_check

mobile-verify:
	@echo "${BLUE}Running mobile backend readiness checks...${NC}"
	$(PYTHON) manage.py check
	$(PYTHON) manage.py migrate --check
	$(MAKE) mobile-infra-check PYTHON=$(PYTHON)
	$(MAKE) mobile-contract PYTHON=$(PYTHON)
	$(MAKE) mobile-test PYTHON=$(PYTHON)
	@echo "${GREEN}Mobile backend readiness checks passed.${NC}"

# Database
db-backup:
	@echo "${GREEN}Backing up database...${NC}"
	mkdir -p backups
	docker-compose exec db pg_dump -U campushub campushub > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "${GREEN}Backup complete!${NC}"

db-restore:
	@echo "${YELLOW}Restoring database...${NC}"
	@echo "${YELLOW}Warning: This will overwrite existing data!${NC}"
	@read -p "Enter backup file name: " filename; \
	docker-compose exec -T db psql -U campushub campushub < backups/$$filename
	@echo "${GREEN}Database restored!${NC}"

# Cleanup
clean:
	docker-compose down -v
	rm -rf __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

prune:
	docker system prune -f

# Quick commands
restart:
	docker-compose restart web

restart-redis:
	docker-compose restart redis

reload:
	docker-compose exec web python manage.py reload

# Mobile development
mobile-dev:
	@echo "${GREEN}Starting mobile-friendly development server...${NC}"
	ALLOWED_HOSTS='*' docker-compose up -d
	@echo ""
	@echo "${GREEN}API available at:${NC}"
	@echo "  http://localhost:8000"
	@echo ""
	@echo "${GREEN}API endpoints:${NC}"
	@echo "  Auth: http://localhost:8000/api/mobile/login/"
	@echo "  Resources: http://localhost:8000/api/mobile/resources/"
	@echo "  Dashboard: http://localhost:8000/api/mobile/dashboard/"
	@echo "  API Info: http://localhost:8000/api/mobile/info/"
