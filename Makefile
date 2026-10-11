# Makefile — convenience wrapper for common dev tasks.
# Requires: uv (Python), Docker (for `make db-*` targets).
#
# DB-dependent targets (migrate, dev, test, shell) list `db-up` as a
# prerequisite. Compose tracks container state itself: `up -d --wait`
# reconciles and blocks until the db healthcheck passes, so depending on
# it is idempotent and a separate lockfile would only be able to drift.

DB        := db
PY        := uv run --group test
PY_NO_T   := uv run

.PHONY: help db-up db-down db-reset migrate dev test shell check coverage

# Default target: show available commands.
help:
	@echo "Available targets:"
	@echo "  make help        - Show this help message"
	@echo "  make db-up        - Start Postgres container, wait until healthy"
	@echo "  make db-down      - Stop Postgres container (data volume intact)"
	@echo "  make db-reset     - Wipe and recreate Postgres (destroys all data)"
	@echo "  make migrate      - Apply migrations"
	@echo "  make dev          - Run Django dev server"
	@echo "  make test         - Run the test suite"
	@echo "  make coverage     - Run tests + Python/template coverage + SQL snapshots"
	@echo "  make shell        - Django shell"
	@echo "  make check        - Django system checks"

# Start Postgres, or block until an already-running container reports healthy.
# Data persists in named volume `drover-pgdata`.
db-up:
	docker compose up -d --wait $(DB)

# Stop Postgres container (data volume intact)
db-down:
	docker compose down

# Wipe and recreate Postgres (destroys all data)
db-reset:
	docker compose down -v
	docker compose up -d --wait $(DB)

# Apply migrations
migrate: db-up
	$(PY_NO_T) python manage.py migrate

# Run dev server
dev: db-up
	$(PY_NO_T) python manage.py runserver

# Run tests
test: db-up
	$(PY) python manage.py test

# Run pytest + Python/template coverage; SQL snapshot drift prints an inline TUI diff.
coverage: db-up
	TEMPLATE_DEBUG=True $(PY) coverage run -m pytest --inline-snapshot=report
	$(PY) coverage report
	$(PY) coverage html

# Interactive shell
shell: db-up
	$(PY_NO_T) python manage.py shell

# Django system checks
check:
	$(PY_NO_T) python manage.py check
