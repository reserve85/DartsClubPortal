"""Send the monthly Elo summary by hand (normally the scheduler does it)."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from app.elo.notify import send_monthly_summaries


class Command(BaseCommand):
    help = "Send the monthly Elo summary (default: last month, only once per month)."

    def add_arguments(self, parser):
        parser.add_argument("--month", help="YYYY-MM (default: last month)")
        parser.add_argument("--force", action="store_true", help="send even if already sent")

    def handle(self, *args, month=None, force=False, **opts):
        start = None
        if month:
            try:
                year, mon = (int(x) for x in month.split("-"))
                start = date(year, mon, 1)
            except ValueError as exc:
                raise CommandError("--month must look like 2026-10") from exc
        sent = send_monthly_summaries(month_start=start, force=force)
        self.stdout.write(self.style.SUCCESS(f"{sent} summary mail(s) sent."))
