"""Matchdays as a calendar feed (iCalendar) to subscribe to on the phone.

The feed comes from the portal, not from nuLiga: it also holds matchdays
entered or managed by hand (a time agreed with the opponent), and matchdays
that left the nuLiga schedule show as cancelled. The address carries a
signed token (no login - calendar apps cannot log in); it only reveals the
matchdays, which are public in nuLiga anyway.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core import signing
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.views import View

from app.matchdays.models import Matchday

SALT = "matchday-calendar"
PAST_DAYS = 90
LENGTH = timedelta(hours=4)
CRLF = chr(13) + chr(10)
REMINDERS = ("-PT4H", "-PT90M")


def token_for(team_id: int | None) -> str:
    """``None`` = every team."""
    return signing.dumps({"t": team_id or 0}, salt=SALT, compress=True)


def team_for_token(token: str) -> int | None:
    try:
        data = signing.loads(token, salt=SALT)
    except signing.BadSignature as exc:
        raise Http404 from exc
    return data.get("t") or None


def calendar_links(request, teams, own: set[int]) -> list[dict]:
    """Subscribe links: the own teams first, then the others, then every team."""
    from app.notifications.services import absolute_url

    def link(team_id, name):
        url = absolute_url(reverse("matchdays:calendar", args=[token_for(team_id)]), request)
        return {
            "team": name,
            "own": team_id in own,
            "url": url,
            "webcal": "webcal://" + url.split("://", 1)[-1],
        }

    rows = [link(t.pk, t.name) for t in teams]
    rows.sort(key=lambda r: (not r["own"], r["team"]))
    if len(rows) > 1:
        from django.utils.translation import gettext as _

        rows.append(link(None, str(_("All teams"))))
    return rows


def _text(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Lines longer than 75 octets continue on the next line (RFC 5545)."""
    out, current = [], ""
    for char in line:
        if len((current + char).encode("utf-8")) > 75:
            out.append(current)
            current = " " + char
        else:
            current += char
    out.append(current)
    return "\r\n".join(out)


def _utc(moment: datetime) -> str:
    return moment.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")


def _venue_lines(location: str) -> list[str]:
    """ "Hall (0903): Street 1, 63814 Town" -> ["Hall (0903)", "Street 1", "63814 Town"]."""
    name, sep, address = location.partition(": ")
    if not sep:
        return [location]
    return [name.strip(), *[part.strip() for part in address.split(", ") if part.strip()]]


def build_calendar(matchdays, name: str, host: str) -> str:
    """One event per matchday, in the style the club already uses:
    "[H] Home - Guest" / "[A] Home - Guest", 4 hours, start time and venue
    address in the description."""
    from django.utils.translation import gettext as _

    local = ZoneInfo(settings.TIME_ZONE)
    stamp = _utc(timezone.now())
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DartsClubPortal//Matchdays//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_text(name)}",
        f"X-WR-TIMEZONE:{settings.TIME_ZONE}",
        "X-PUBLISHED-TTL:PT6H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
    ]
    for md in matchdays:
        home = md.venue == "home"
        lines += ["BEGIN:VEVENT", f"UID:matchday-{md.pk}@{host}", f"DTSTAMP:{stamp}"]
        if md.start_time:
            start = datetime.combine(md.date, md.start_time, tzinfo=local)
            lines += [f"DTSTART:{_utc(start)}", f"DTEND:{_utc(start + LENGTH)}"]
        else:
            lines += [
                f"DTSTART;VALUE=DATE:{md.date:%Y%m%d}",
                f"DTEND;VALUE=DATE:{md.date + timedelta(days=1):%Y%m%d}",
            ]
        pair = f"{md.team.name} - {md.opponent}" if home else f"{md.opponent} - {md.team.name}"
        lines.append(f"SUMMARY:{_text(('[H] ' if home else '[A] ') + pair)}")
        details = []
        if md.start_time:
            details += [_("Match start: %(time)s") % {"time": f"{md.start_time:%H:%M}"}, ""]
        if md.location:
            details += _venue_lines(md.location)
            lines.append(f"LOCATION:{_text(md.location)}")
        if md.description:
            details += ["", md.description]
        while details and not details[-1]:
            details.pop()
        if details:
            lines.append(f"DESCRIPTION:{_text(chr(10).join(details))}")
        lines.append("STATUS:CANCELLED" if md.nuliga_removed else "STATUS:CONFIRMED")
        lines.append("TRANSP:OPAQUE")
        if md.start_time and not md.nuliga_removed:
            # Default reminders: 4 hours and 90 minutes before the start.
            for trigger in REMINDERS:
                lines += [
                    "BEGIN:VALARM",
                    "ACTION:DISPLAY",
                    f"DESCRIPTION:{_text(pair)}",
                    f"TRIGGER:{trigger}",
                    "END:VALARM",
                ]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return CRLF.join(_fold(line) for line in lines) + CRLF


class MatchdayCalendarView(View):
    """GET <token>.ics - no login (calendar apps), the token picks the team."""

    def get(self, request, token):
        from app.teams.models import Team

        team_id = team_for_token(token)
        since = timezone.localdate() - timedelta(days=PAST_DAYS)
        matchdays = (
            Matchday.objects.filter(date__gte=since)
            .select_related("team")
            .order_by("date", "start_time", "pk")
        )
        name = getattr(settings, "SITE_NAME", "Darts Club Portal")
        if team_id is not None:
            team = Team.objects.filter(pk=team_id).first()
            if team is None:
                raise Http404
            matchdays = matchdays.filter(team=team)
            name = team.name
        from django.utils import translation

        with translation.override(settings.LANGUAGE_CODE):  # calendar apps send no language
            body = build_calendar(matchdays, name, request.get_host().split(":")[0])
        response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
        response["Content-Disposition"] = 'inline; filename="matchdays.ics"'
        response["Cache-Control"] = "no-cache"
        return response
