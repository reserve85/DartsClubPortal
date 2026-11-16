"""manage.py import_elo <file> [--dry-run] [--replace] [--email-domain example.org]"""

from django.core.management.base import BaseCommand, CommandError

from app.importer.elo_import import import_elo
from app.importer.report import ImportAborted


class Command(BaseCommand):
    help = "Import an EloRankingSystem database (players, matches, accounts)."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--dry-run", action="store_true", help="preview only, nothing is saved")
        parser.add_argument("--replace", action="store_true", help="delete existing Elo data first")
        parser.add_argument(
            "--email-domain", default="elo.invalid", help="for accounts without e-mail"
        )
        parser.add_argument(
            "--map-account",
            action="append",
            default=[],
            metavar="NAME=EMAIL",
            help="link an Elo login to an existing portal account (repeatable)",
        )

    def handle(self, path, dry_run=False, replace=False, email_domain="elo.invalid", **opts):
        mapping = dict(item.split("=", 1) for item in opts.get("map_account") or [] if "=" in item)
        try:
            report = import_elo(
                path,
                dry_run=dry_run,
                replace=replace,
                email_domain=email_domain,
                account_map=mapping,
            )
        except ImportAborted as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(report.as_text())
        if not report.ok:
            raise CommandError("Verification failed - see the report above.")
