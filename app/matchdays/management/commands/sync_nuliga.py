"""Import the nuLiga schedules (normally the in-process scheduler does it daily)."""

from django.core.management.base import BaseCommand

from app.matchdays.models import NuligaLink
from app.matchdays.nuliga import NuligaError, summary_lines, sync_due, sync_link


class Command(BaseCommand):
    help = "Import the matchdays from nuLiga: today's due teams, or every team with --all."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="every linked team, now")
        parser.add_argument("--quiet-captains", action="store_true", help="no notifications")

    def handle(self, *args, all=False, quiet_captains=False, **opts):
        if not all:
            self.stdout.write(f"{sync_due()} team(s) imported.")
            return
        for link in NuligaLink.objects.select_related("team", "season"):
            try:
                result = sync_link(link, notify=not quiet_captains)
            except NuligaError as exc:
                self.stdout.write(self.style.ERROR(f"{link}: {exc}"))
                continue
            self.stdout.write(self.style.SUCCESS(f"{link} ({link.nuliga_name}):"))
            for line in summary_lines(result) or ["-"]:
                self.stdout.write(f"  {line}")
