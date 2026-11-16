"""manage.py import_penalty <file> [--dry-run]"""

from django.core.management.base import BaseCommand, CommandError

from app.importer.penalty_import import import_penalty
from app.importer.report import ImportAborted


class Command(BaseCommand):
    help = "Import a DartsPenaltySystem database (accounts, teams, penalties, payments)."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--dry-run", action="store_true", help="preview only, nothing is saved")

    def handle(self, path, dry_run=False, **opts):
        try:
            report = import_penalty(path, dry_run=dry_run)
        except ImportAborted as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(report.as_text())
        if not report.ok:
            raise CommandError("Verification failed - see the report above.")
