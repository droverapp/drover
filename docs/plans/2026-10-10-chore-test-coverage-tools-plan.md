---
title: "chore: add Django template and query coverage tooling"
type: plan
date: 2026-10-10
status: complete
confidence: high
---

# Add Django template and SQL query coverage tooling

## Problem Statement

The project needs a way to report which Django template lines execute during tests and to snapshot the SQL query shapes exercised by integration tests.

## Target End State

Coverage.py reports Python and Django template line coverage. Developers can run a documented Make target to generate the report on Python 3.13/PostgreSQL. Tests can use `inline-snapshot-django` to assert fingerprinted SQL query sequences.

## Scope and Non-Goals

- Add test-only dependencies and coverage configuration.
- Enable template debug mode only when requested for coverage, not in production by default.
- Add a Makefile target for coverage execution/reporting.
- Exercise query snapshots from real integration tests included in the coverage run.
- Do not claim or produce a global query-variant percentage: SQL snapshots record only exercised paths and have no automatic denominator.

## Proposed Solution

Add `coverage[toml]`, `django-coverage-plugin`, `inline-snapshot-django`, `pytest`, and `pytest-django` to an opt-in `test` dependency group. Configure template coverage and pytest discovery for Django apps' `tests.py` files. Run `make coverage` through pytest in inline-snapshot report mode so query-shape drift produces a terminal diff report.

## Implementation Tasks

- [x] Add coverage and template-plugin configuration/dependencies.
- [x] Add `inline-snapshot-django` as a test-only dependency.
- [x] Add the coverage-only template debug switch and Make target.
- [x] Run the full suite under coverage on PostgreSQL; verify templates appear in report and the SQL snapshot API imports.
- [x] Add pytest-django and configure discovery for app `tests.py` files.
- [x] Run `make coverage` through pytest with inline-snapshot report mode.
- [x] Add SQL snapshots to RSVP view/query integration tests.
- [x] Re-run normal `make test` and coverage-enabled tests.

## Acceptance Criteria

- `make coverage` runs the full suite against configured PostgreSQL and generates a coverage report including Django templates.
- Production/default template debug remains controlled by `DEBUG`; coverage explicitly enables template debug.
- `inline_snapshot_django.snapshot_queries` is importable in the dev environment.
- Existing full suite passes; normal `make test` behavior is unchanged.
