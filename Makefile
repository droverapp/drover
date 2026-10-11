# Makefile — convenience wrapper for common dev tasks.
# Requires: uv (Python), Docker (for `make db-*` targets).
#
# DB-dependent targets (migrate, dev, test, shell) list `db-up` as a
# prerequisite. Compose tracks container state itself: `up -d --wait`
# reconciles and blocks until the db healthcheck passes, so depending on
# it is idempotent and a separate lockfile would only be able to drift.

.PHONY: db-up db-down db-reset migrate dev test shell check

# Start Postgres, or block until an already-running container reports healthy.
# Data persists in named volume `drover-pgdata`.
db-up:
	docker compose up -d --wait db

# Stop Postgres container (data volume intact)
db-down:
	docker compose down

# Wipe and recreate Postgres (destroys all data)
db-reset:
	docker compose down -v
	docker compose up -d --wait db

# Apply migrations
migrate: db-up
	uv run python manage.py migrate

# Run dev server
dev: db-up
	uv run python manage.py runserver

# Run tests
test: db-up
	uv run python manage.py test

# Interactive shell
shell: db-up
	uv run python manage.py shell

# Django system checks
check:
	uv run python manage.py check