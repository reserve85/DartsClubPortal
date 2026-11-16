"""Elo messaging: match notifications and the monthly Elo summary.

- Match entered / edited / deleted: an in-app notification for both players'
  accounts (not for the person who made the change) and - when the account
  keeps "Elo match results" switched on - an e-mail.
- Monthly summary: on the first of a month (after 08:00) every account with a
  linked Elo player and "Monthly Elo summary" switched on gets last month's
  numbers. ``EloMonthlyReport`` remembers sent months, so restarts or the
  hourly scheduler tick never send twice.
"""

import logging
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from app.core.access import has_module
from app.core.modules import ELO, is_enabled

logger = logging.getLogger("app.elo")


def _account(player):
    user = getattr(player, "user", None)
    if user is None or not user.is_active or not has_module(user, ELO):
        return None
    return user


def match_changed(match, *, actor=None, action: str, request=None) -> None:
    """Notify both players about a created / updated / deleted match."""
    from app.notifications.inapp import notify_user
    from app.notifications.services import NotificationService, absolute_url, email_configured
    from app.notifications.unsubscribe import mail_context

    for player, opponent, side in (
        (match.player_a, match.player_b, "a"),
        (match.player_b, match.player_a, "b"),
    ):
        user = _account(player)
        if user is None or (actor is not None and user.pk == getattr(actor, "pk", None)):
            continue
        mine = getattr(match, f"score_{side}")
        theirs = getattr(match, f"score_{'b' if side == 'a' else 'a'}")
        change = getattr(match, f"elo_change_{side}")

        def verb(a=action, o=opponent, m=mine, t=theirs, c=change):
            if a == "deleted":
                return _("Elo match deleted: you vs %(opp)s %(m)s:%(t)s") % {
                    "opp": o.name,
                    "m": m,
                    "t": t,
                }
            text = _("Elo match vs %(opp)s: %(m)s:%(t)s (%(c)s Elo)") % {
                "opp": o.name,
                "m": m,
                "t": t,
                "c": f"{c:+.1f}",
            }
            return (_("Corrected: ") + text) if a == "updated" else text

        notify_user(
            recipient=user,
            verb=verb,
            sender=actor if getattr(actor, "is_authenticated", False) else None,
            level="info",
        )
        if not user.elo_match_notify or not user.email or not email_configured():
            continue
        lang = user.preferred_language or settings.LANGUAGE_CODE
        with translation.override(lang):
            subject = str(verb())
        ctx = {
            "player": player,
            "opponent": opponent,
            "match": match,
            "action": action,
            "mine": mine,
            "theirs": theirs,
            "change": change,
            "won": match.winner_id == player.pk,
            "elo_after": getattr(match, f"elo_after_{side}"),
            "match_url": absolute_url(reverse("elo:match_detail", args=[match.pk]), request)
            if action != "deleted"
            else absolute_url(reverse("elo:ranking"), request),
            **mail_context(user, "elo_match"),
        }
        NotificationService().send_templated(
            recipients=[user],
            template_base="emails/elo_match",
            subject=subject,
            context=ctx,
            language=lang,
        )


# ----------------------------------------------------------- monthly summary
def previous_month(today: date | None = None) -> tuple[date, date]:
    today = today or timezone.localdate()
    end = today.replace(day=1) - timedelta(days=1)
    return end.replace(day=1), end


def summary_for(player_id: int, start: date, end: date, ranking=None) -> dict | None:
    """Numbers of one player for the month - None when not in the ranking."""
    from app.elo.services import ranking as ranking_service

    ranking = ranking or ranking_service.generate_ranking(start, end, include_inactive=True)
    entry = next((e for e in ranking.entries if e.player_id == player_id), None)
    if entry is None:
        return None
    stats = ranking_service.player_statistics(player_id, start, end)["period"]
    return {"entry": entry, "stats": stats, "field_size": ranking.field_size}


def send_monthly_summaries(*, month_start: date | None = None, force: bool = False) -> int:
    """Send last month's summary to every subscribed account. Returns mails sent."""
    from django.contrib.auth import get_user_model

    from app.elo.models import EloMonthlyReport, EloProfile
    from app.elo.services import ranking as ranking_service
    from app.notifications.services import NotificationService, absolute_url, email_configured
    from app.notifications.unsubscribe import mail_context

    if not is_enabled(ELO):
        return 0
    if month_start is None:
        start, end = previous_month()
    else:
        start = month_start.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    if not force:
        try:
            with transaction.atomic():
                EloMonthlyReport.objects.create(month=start)
        except IntegrityError:
            return 0  # already sent (or being sent) for this month
    ranking = ranking_service.generate_ranking(start, end, include_inactive=True)
    shown = [e for e in ranking.entries if e.matches > 0]
    table = sorted(ranking.entries, key=lambda e: e.position)
    top = table[:5]
    mover = max(shown, key=lambda e: e.elo_change, default=None)
    if mover is not None and mover.elo_change <= 0:
        mover = None
    jumper = max(
        (e for e in table if e.position_change and e.position_change > 0),
        key=lambda e: (e.position_change, -e.position),
        default=None,
    )
    busiest = max(shown, key=lambda e: (e.matches, e.wins), default=None)
    logo_url = _logo_absolute_url()
    month_matches = sum(e.matches for e in ranking.entries) // 2
    elo_players = set(EloProfile.objects.values_list("player_id", flat=True))
    users = (
        get_user_model()
        .objects.filter(is_active=True, elo_monthly_summary=True, player_link_id__in=elo_players)
        .exclude(email="")
    )
    if not email_configured():
        logger.info("Monthly Elo summary skipped: e-mail not configured.")
        return 0
    sent = 0
    for user in users:
        if not has_module(user, ELO):
            continue
        data = summary_for(user.player_link_id, start, end, ranking)
        if data is None:
            continue
        lang = user.preferred_language or settings.LANGUAGE_CODE
        with translation.override(lang):
            subject = _("Your Elo month %(month)s") % {"month": start.strftime("%m/%Y")}
        sent += NotificationService().send_templated(
            recipients=[user],
            template_base="emails/elo_monthly",
            subject=subject,
            language=lang,
            context={
                "player": user.player_link,
                "month": start,
                "month_end": end,
                "me": data["entry"],
                "stats": data["stats"],
                "field_size": data["field_size"],
                "top": top,
                "table": table,
                "mover": mover,
                "jumper": jumper,
                "busiest": busiest,
                "logo_url": logo_url,
                "month_matches": month_matches,
                "ranking_url": absolute_url(
                    reverse("elo:ranking") + f"?period=custom&from={start}&to={end}"
                ),
                **mail_context(user, "elo_monthly"),
            },
        )
    logger.info("Monthly Elo summary %s sent to %s account(s).", start, sent)
    return sent


def _logo_absolute_url() -> str:
    """Absolute URL of the club logo (light variant first) for the mail header."""
    from app.core.branding import logo_urls
    from app.notifications.services import absolute_url

    urls = logo_urls()
    path = urls.get("light") or urls.get("dark") or ""
    if not path:
        return ""
    url = absolute_url(path)
    return url if url.startswith("http") else ""


def monthly_summary_due(now: datetime | None = None) -> bool:
    """1st-3rd of the month from 08:00 (club time zone) - a server that was
    down on the 1st still catches up; ``EloMonthlyReport`` prevents repeats."""
    now = timezone.localtime(now)
    return now.day <= 3 and (now.day > 1 or now.hour >= 8)


def maybe_send_monthly(now: datetime | None = None) -> int:
    """Scheduler hook: send last month's summaries once when due."""
    if not is_enabled(ELO) or not monthly_summary_due(now):
        return 0
    from app.elo.models import EloMonthlyReport

    start, _end = previous_month(timezone.localtime(now).date())
    if EloMonthlyReport.objects.filter(month=start).exists():
        return 0
    return send_monthly_summaries(month_start=start)
