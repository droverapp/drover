# Makefile — convenience wrapper for common dev tasks.
# Requires: uv (Python), Docker (for `make db-*` targets).

.PHONY: db-up db-down db-reset migrate dev test shell check

# Start Postgres container (data persists in named volume `drover-pgdata`)
db-up:
	docker compose up -d db

# Stop Postgres container (data volume intact)
db-down:
	docker compose down

# Wipe and recreate Postgres (destroys all data)
db-reset:
	docker compose down -v
	docker compose up -d db

# Apply migrations
migrate:
	uv run python manage.py migrate

# Run dev server
dev:
	uv run python manage.py runserver

# Run tests
test:
	uv run python manage.py test

# Interactive shell
shell:
	uv run python manage.py shell

# Django system checks
check:
	uv run python manage.py check