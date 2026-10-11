"""Preflight guard for the 2026-10 UUID primary-key release.

That release deleted the entire migration history and regenerated it under
previously recorded names (``users/0001_initial``, ``groups/0001_initial``)
with a different schema, plus a brand-new ``groups/0002_initial``. ``migrate``
against a database created before the cutover half-applies that schema and
crashes mid-ALTER -- on Heroku, whose boot command runs ``migrate``, that
means a broken release after the fact. This command refuses instead, so the
boot fails before anything is touched.

Checks against the default database:

1. Ghost migrations: rows in ``django_migrations`` whose (app, name) no
   longer exist in the migration graph -- the history was rewritten under
   this database, so its schema is the pre-cutover one.
2. Column type: a ``users`` table exists but its ``id`` column is not
   Postgres ``uuid`` (the pre-cutover integer primary key).

A database where neither check fires is either empty (fresh start -- the
expected target for this release) or already cut over, and passes.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.loader import MigrationLoader

RESET_HINT = """\
This database predates the UUID primary-key release and cannot be migrated
in place; its old migration history was deliberately squashed away. Options:

  * Fresh start (what this release expects):
        heroku pg:reset DATABASE_URL --app <app>
    then redeploy -- preflight and migrate will pass. All existing rows are
    lost; take a pg:dump first if any matter.

  * Keep the data: restore into an empty database and rewrite every int PK
    plus all referencing FK columns to new UUIDs. There is no in-place path.
"""


class Command(BaseCommand):
    help = "Exit non-zero unless the database is compatible with the UUID-PK release."

    def handle(self, *args, **options):
        try:
            problems = list(self._problems())
        except Exception as exc:  # an unreachable DB is also not deploy-ready
            raise CommandError(f"preflight: cannot inspect database: {exc}") from exc

        if problems:
            self.stderr.write("preflight: database is NOT ready for this release:")
            for problem in problems:
                self.stderr.write(f"  - {problem}")
            raise CommandError("\n" + RESET_HINT)

        self.stdout.write(
            self.style.SUCCESS("preflight: database compatible with UUID-PK release.")
        )

    def _problems(self):
        table = get_user_model()._meta.db_table

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'django_migrations')"
            )
            has_recorder = cursor.fetchone()[0]

        if has_recorder:
            loader = MigrationLoader(connection, ignore_no_migrations=True)
            ghosts = sorted(set(loader.applied_migrations) - set(loader.graph.nodes))
            if ghosts:
                sample = ", ".join(f"{app}/{name}" for app, name in ghosts[:5])
                more = f" (+{len(ghosts) - 5} more)" if len(ghosts) > 5 else ""
                yield (
                    f"{len(ghosts)} recorded migrations no longer exist on disk: "
                    f"{sample}{more}"
                )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = 'id'",
                (table,),
            )
            row = cursor.fetchone()
        if row and row[0].lower() != "uuid":
            yield f"{table}.id has type {row[0]!r}, expected 'uuid'"
