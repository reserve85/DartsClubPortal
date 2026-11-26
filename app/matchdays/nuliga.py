"""nuLiga import: keep a team's matchdays in line with its nuLiga schedule.

Every team page on nuLiga (``.../wa/teamPortrait?teamtable=...``) links a
calendar feed (``getTeamMeetingsWebcal``). Each match in it has a stable UID,
date and time, home and guest team, league, match number and the venue
address. The import

* creates the matchdays of the season (or adopts a matchday entered by hand
  on the same day),
* follows changes: new date or time, home/away, opponent, venue,
* marks matchdays that left the schedule as "removed in nuLiga" - it never
  deletes anything, penalties may already hang on a matchday,
* tells the team's captain (in the app and by e-mail) what changed.

It runs once a day (in-process scheduler, from 06:00) for the default
season and on demand ("Sync with nuLiga" on the matchday list). Only
``https://*.liga.nu`` addresses are fetched.
"""

import html
import logging
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, time
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from app.matchdays.models import Matchday, NuligaLink, Season, VenueChoice

logger = logging.getLogger("app.matchdays")

DAILY_FROM = time(6, 0)
MAX_BYTES = 2_000_000
TIMEOUT = 20
FEED_HREF = re.compile(r"""href\s*=\s*["']([^"']*getTeamMeetingsWebcal[^"']*)["']""", re.IGNORECASE)


class NuligaError(Exception):
    """A readable reason why the import did not work (shown to the admins)."""


# ------------------------------------------------------------------ fetching
def check_url(url: str) -> str:
    """Return the URL as https, or raise when it is no nuLiga address."""
    url = (url or "").strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://") :]
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not (host == "liga.nu" or host.endswith(".liga.nu")):
        raise NuligaError(_("Only nuLiga addresses (https://….liga.nu/…) are allowed."))
    return url


def _fetch(url: str) -> str:
    from app.core.version import GITHUB_REPO_URL

    request = urllib.request.Request(
        check_url(url),
        headers={"User-Agent": f"DartsClubPortal (+{GITHUB_REPO_URL})"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read(MAX_BYTES + 1)
            charset = response.headers.get_content_charset() or "utf-8"
    except Exception as exc:
        raise NuligaError(_("nuLiga could not be reached: %(error)s") % {"error": exc}) from exc
    if len(raw) > MAX_BYTES:
        raise NuligaError(_("The nuLiga answer is unexpectedly large."))
    return raw.decode(charset, errors="replace")


def feed_url_for(team_url: str) -> str:
    """The calendar feed of a nuLiga team page (or the feed URL itself)."""
    url = check_url(team_url)
    if "getTeamMeetingsWebcal" in url:
        return url
    match = FEED_HREF.search(_fetch(url))
    if match is None:
        raise NuligaError(
            _("No calendar found on this page. Please use the link of the team page (Mannschaft).")
        )
    return check_url(urljoin(url, html.unescape(match.group(1))))


# ------------------------------------------------------------------- parsing
@dataclass
class Event:
    uid: str
    day: date
    start: time | None
    home: str
    guest: str
    league: str = ""
    number: str = ""
    location: str = ""
    cancelled: bool = False


def _unescape(value: str) -> str:
    return (
        value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";")
    ).replace("\\\\", "\\")


def _when(params: str, value: str) -> tuple[date, time | None]:
    value = value.strip()
    if "VALUE=DATE" in params.upper() and "T" not in value:
        return datetime.strptime(value[:8], "%Y%m%d").date(), None
    moment = datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    local = ZoneInfo(settings.TIME_ZONE)
    if value.endswith("Z"):
        moment = moment.replace(tzinfo=ZoneInfo("UTC")).astimezone(local)
    else:
        tz = re.search(r"TZID=([^;:]+)", params)
        if tz:
            try:
                moment = moment.replace(tzinfo=ZoneInfo(tz.group(1))).astimezone(local)
            except (KeyError, ValueError):  # unknown zone: keep the wall-clock time
                logger.info("nuLiga: unknown time zone %s.", tz.group(1))
    return moment.date(), moment.time().replace(second=0, microsecond=0)


def parse_feed(text: str) -> list[Event]:
    """The matches of an iCalendar feed (only what the import needs)."""
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]  # folded line
        else:
            lines.append(raw)
    events, props = [], None
    for line in lines:
        if line == "BEGIN:VEVENT":
            props = {}
        elif line == "END:VEVENT" and props is not None:
            event = _event(props)
            if event is not None:
                events.append(event)
            props = None
        elif props is not None and ":" in line:
            head, value = line.split(":", 1)
            name, _sep, params = head.partition(";")
            props[name.upper()] = (params, value)
    return events


def _event(props: dict) -> Event | None:
    if "UID" not in props or "DTSTART" not in props:
        return None
    day, start = _when(*props["DTSTART"])
    info = {}
    description = _unescape(props.get("DESCRIPTION", ("", ""))[1])
    lines = [line.strip() for line in description.split("\n") if line.strip()]
    for line in lines:
        key, sep, value = line.partition(":")
        if sep:
            info[key.strip().lower()] = value.strip()
    home, guest = info.get("heim", ""), info.get("gast", "")
    if not (home and guest):  # fall back to "League Home vs Guest (nr)"
        summary = _unescape(props.get("SUMMARY", ("", ""))[1])
        found = re.search(r"(.+?) vs (.+?)(?: \(\d+\))?$", summary)
        if found is None:
            return None
        home, guest = found.group(1).strip(), found.group(2).strip()
    status = props.get("STATUS", ("", ""))[1].strip().upper()
    return Event(
        uid=props["UID"][1].strip(),
        day=day,
        start=start,
        home=home,
        guest=guest,
        league=lines[0] if lines and ":" not in lines[0] else "",
        number=info.get("begegnungs-nr", ""),
        location=_unescape(props.get("LOCATION", ("", ""))[1]).strip()[:255],
        cancelled=status == "CANCELLED",
    )


def own_team(events: list[Event]) -> str:
    """The nuLiga name of the team: the one that plays in every match."""
    common = None
    for event in events:
        names = {event.home, event.guest}
        common = names if common is None else common & names
    if common and len(common) == 1:
        return next(iter(common))
    counts: dict[str, int] = {}
    for event in events:
        for name in (event.home, event.guest):
            counts[name] = counts.get(name, 0) + 1
    return max(counts, key=counts.get) if counts else ""


# ------------------------------------------------------------------- syncing
@dataclass
class SyncResult:
    created: list = field(default_factory=list)
    adopted: list = field(default_factory=list)
    changed: list = field(default_factory=list)  # (matchday, [change texts])
    removed: list = field(default_factory=list)
    first: bool = False

    @property
    def anything(self) -> bool:
        return bool(self.created or self.adopted or self.changed or self.removed)


def _description(event: Event) -> str:
    parts = [event.league, _("Match no. %(n)s") % {"n": event.number} if event.number else ""]
    return " · ".join(p for p in parts if p)[:255]


def _venue_label(value: str) -> str:
    return str(dict(VenueChoice.choices).get(value, value))


def sync_link(link: NuligaLink, *, notify: bool = True, actor=None) -> SyncResult:
    """Import the feed of one team page; returns what changed."""
    result = SyncResult(first=link.last_sync_at is None)
    link.last_sync_at = timezone.now()
    try:
        if not link.feed_url:
            link.feed_url = feed_url_for(link.team_url)
        events = parse_feed(_fetch(link.feed_url))
        if not events:
            raise NuligaError(_("The nuLiga calendar of this team is empty."))
        name = own_team(events)
        with transaction.atomic():
            _apply(link, events, name, result)
        link.nuliga_name = name[:255]
        link.last_error = ""
    except NuligaError as exc:
        link.last_error = str(exc)[:500]
        link.save(update_fields=["last_sync_at", "last_error", "feed_url"])
        logger.warning("nuLiga import failed for %s: %s", link, exc)
        raise
    link.save(update_fields=["last_sync_at", "last_error", "feed_url", "nuliga_name"])
    if notify and result.anything:
        notify_captains(link, result)
    return result


def _values(event: Event, name: str) -> dict:
    home = event.home == name
    return {
        "date": event.day,
        "start_time": event.start,
        "opponent": (event.guest if home else event.home)[:255],
        "venue": VenueChoice.HOME if home else VenueChoice.AWAY,
        "location": event.location,
    }


def _apply(link: NuligaLink, events: list[Event], name: str, result: SyncResult) -> None:
    matchdays = Matchday.objects.filter(team=link.team, season=link.season)
    by_uid = {m.nuliga_uid: m for m in matchdays.exclude(nuliga_uid="")}
    manual = list(matchdays.filter(nuliga_uid=""))
    events = [e for e in events if not e.cancelled]
    seen = {e.uid for e in events}
    found: dict[str, tuple] = {}  # uid -> (matchday, adopted?)

    # 1. Known matches, then matchdays entered by hand on the same day.
    for event in events:
        if event.uid in by_uid:
            found[event.uid] = (by_uid[event.uid], False)
            continue
        same_day = next((m for m in manual if m.date == event.day), None)
        if same_day is not None:
            manual.remove(same_day)
            found[event.uid] = (same_day, True)
    # 2. Moved in nuLiga before the import: same opponent - first with the
    #    same home/away, then (home right swapped) any; the closest date wins.
    for same_venue in (True, False):
        for event in events:
            if event.uid in found:
                continue
            values = _values(event, name)
            fits = [
                m
                for m in manual
                if (m.venue == values["venue"] or not same_venue)
                and m.opponent.strip().casefold() == values["opponent"].strip().casefold()
            ]
            if fits:
                best = min(fits, key=lambda m: abs((m.date - event.day).days))
                manual.remove(best)
                found[event.uid] = (best, True)

    for event in events:
        values = _values(event, name)
        matchday, adopted = found.get(event.uid, (None, False))
        if matchday is None:
            matchday = Matchday(
                team=link.team,
                season=link.season,
                description=_description(event),
                nuliga_uid=event.uid,
                **values,
            )
            matchday.save()
            result.created.append(matchday)
            continue
        if adopted:
            matchday.nuliga_uid = event.uid
            if not matchday.description:
                matchday.description = _description(event)
        changes = _changes(matchday, values)
        if adopted:
            # A new start time or address on the same day is no news.
            changes = [c for c in changes if matchday.date != values["date"] and c]
        for key, value in values.items():
            setattr(matchday, key, value)
        if matchday.nuliga_removed:
            matchday.nuliga_removed = False
            changes.append(str(_("back in the nuLiga schedule")))
        matchday.save()
        if adopted:
            result.adopted.append(matchday)
        if changes:
            result.changed.append((matchday, changes))
    for uid, matchday in by_uid.items():
        if uid not in seen and not matchday.nuliga_removed:
            matchday.nuliga_removed = True
            matchday.save(update_fields=["nuliga_removed"])
            result.removed.append(matchday)


def _changes(matchday: Matchday, values: dict) -> list[str]:
    out = []
    if matchday.date != values["date"] or matchday.start_time != values["start_time"]:
        old = matchday.date.strftime("%d.%m.%Y") + (
            f" {matchday.start_time:%H:%M}" if matchday.start_time else ""
        )
        new = values["date"].strftime("%d.%m.%Y") + (
            f" {values['start_time']:%H:%M}" if values["start_time"] else ""
        )
        out.append(str(_("moved from %(old)s to %(new)s") % {"old": old, "new": new}))
    if matchday.venue != values["venue"]:
        out.append(str(_("now %(venue)s") % {"venue": _venue_label(values["venue"])}))
    if matchday.opponent != values["opponent"]:
        out.append(str(_("opponent: %(name)s") % {"name": values["opponent"]}))
    if matchday.location != values["location"] and matchday.location:
        out.append(str(_("venue: %(place)s") % {"place": values["location"]}))
    return out


# -------------------------------------------------------------- notification
def _recipients(team):
    from django.contrib.auth import get_user_model

    from app.core.permissions import user_is_penalty_admin

    users = get_user_model().objects.filter(is_active=True)
    captains = list(users.filter(team=team))
    return captains or [u for u in users if user_is_penalty_admin(u)]


def summary_lines(result: SyncResult) -> list[str]:
    def label(m):
        when = m.date.strftime("%d.%m.%Y") + (f" {m.start_time:%H:%M}" if m.start_time else "")
        return f"{when} {_venue_label(m.venue)} – {m.opponent}"

    lines = [_("New: %(m)s") % {"m": label(m)} for m in result.created]
    changed = {m.pk for m, _changes in result.changed}
    lines += [_("Linked: %(m)s") % {"m": label(m)} for m in result.adopted if m.pk not in changed]
    lines += [f"{label(m)}: {', '.join(changes)}" for m, changes in result.changed]
    lines += [_("No longer in nuLiga: %(m)s") % {"m": label(m)} for m in result.removed]
    return lines


def notify_captains(link: NuligaLink, result: SyncResult) -> None:
    """One in-app message and one e-mail per captain with every change."""
    from app.notifications.inapp import notify_user
    from app.notifications.services import NotificationService, absolute_url, email_configured

    url = absolute_url(reverse("matchdays:matchday_list") + f"?team={link.team_id}")
    for user in _recipients(link.team):
        lang = user.preferred_language or settings.LANGUAGE_CODE

        def verb(r=result, t=link.team):
            if r.first:
                return _("nuLiga: %(n)s matchdays of %(team)s imported.") % {
                    "n": len(r.created) + len(r.adopted),
                    "team": t.name,
                }
            return _("nuLiga: the schedule of %(team)s changed (%(n)s).") % {
                "team": t.name,
                "n": len(r.created) + len(r.adopted) + len(r.changed) + len(r.removed),
            }

        notify_user(recipient=user, verb=verb, level="info")
        if not user.email or not email_configured():
            continue
        with translation.override(lang):
            subject = str(verb())
            lines = summary_lines(result)
        NotificationService().send_templated(
            recipients=[user],
            template_base="emails/nuliga_changes",
            subject=subject,
            language=lang,
            context={"team": link.team, "lines": lines, "url": url, "first": result.first},
        )


# ------------------------------------------------------------------- runs
def links_due(now: datetime | None = None):
    """Links of the default season not imported yet today (from 06:00 on)."""
    now = timezone.localtime(now or timezone.now())
    if now.time() < DAILY_FROM:
        return []
    season = Season.default() or Season.objects.order_by("-name").first()
    if season is None:
        return []
    return [
        link
        for link in NuligaLink.objects.filter(season=season).select_related("team", "season")
        if link.last_sync_at is None or timezone.localtime(link.last_sync_at).date() < now.date()
    ]


def sync_due(now: datetime | None = None) -> int:
    """The daily run (scheduler tick / management command). Never raises."""
    done = 0
    for link in links_due(now):
        try:
            sync_link(link)
            done += 1
        except Exception:
            logger.exception("nuLiga import failed for %s.", link)
    return done
