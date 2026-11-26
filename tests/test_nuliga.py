"""nuLiga import: feed parsing, matchday sync, captain notices, rights, daily run."""

from datetime import date, datetime, time, timedelta
from unittest import mock

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from app.matchdays import nuliga
from app.matchdays.models import Matchday, NuligaLink, Season, VenueChoice
from tests.conftest import inertia_props

TEAM_PAGE = (
    "https://bdv-dart.liga.nu/cgi-bin/WebObjects/nuLigaDARTDE.woa/wa/teamPortrait"
    "?teamtable=1&championship=UFr+2026%2F27&group=2"
)
FEED = "https://bdv-dart.liga.nu/cgi-bin/WebObjects/nuLigaDARTDE.woa/wa/getTeamMeetingsWebcal?teamid=7&token=abc%3D"
HTML = f'<p><a href="{FEED.replace("&", "&amp;").replace("https:", "")}">Kalender herunterladen</a></p>'


def _event(uid, when, home, guest, nr, place="Clubheim (0901): Hauptstr. 1\\, 63000 Ort"):
    return (
        "BEGIN:VEVENT\r\n"
        f"DTSTART;TZID=Europe/Berlin:{when}\r\n"
        f"SUMMARY:5. Bezirksliga West 2 {home} vs {guest} ({nr})\r\n"
        f"UID:{uid}\r\n"
        "STATUS:CONFIRMED\r\n"
        f"DESCRIPTION:5. Bezirksliga West 2\\nBegegnungs-Nr: {nr}\\nHeim: {home}\\nGast: {guest}\\nHall\r\n"
        " e: x\\n\r\n"
        f"LOCATION:{place}\r\n"
        "END:VEVENT\r\n"
    )


def _feed(*events):
    return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + "".join(events) + "END:VCALENDAR\r\n"


HOME = _event("u1", "20270109T140000", "Bullseye 1", "SV Gast", 27)
AWAY = _event(
    "u2", "20261023T190000", "DC Heim", "Bullseye 1", 12, "Halle (0902): Weg 2\\, 63111 Dorf"
)


@pytest.fixture
def season(db, team):
    return Season.objects.create(name="2026/2027", is_default=True)


@pytest.fixture
def link(season, team):
    return NuligaLink.objects.create(season=season, team=team, team_url=TEAM_PAGE)


def _serve(feed_text):
    """Fake nuLiga: the team page links the feed, the feed answers ``feed_text``."""
    return mock.patch.object(
        nuliga, "_fetch", side_effect=lambda url: HTML if "teamPortrait" in url else feed_text
    )


class TestFeed:
    def test_parse_events(self):
        events = nuliga.parse_feed(_feed(HOME, AWAY))
        assert [e.uid for e in events] == ["u1", "u2"]
        first = events[0]
        assert first.day == date(2027, 1, 9) and first.start == time(14, 0)
        assert (first.home, first.guest, first.number) == ("Bullseye 1", "SV Gast", "27")
        assert first.league == "5. Bezirksliga West 2"
        assert first.location == "Clubheim (0901): Hauptstr. 1, 63000 Ort"
        assert nuliga.own_team(events) == "Bullseye 1"

    def test_only_nuliga_addresses(self):
        assert nuliga.check_url("webcal://x.liga.nu/a").startswith("https://x.liga.nu/")
        for bad in ("https://evil.example/liga.nu", "http://bdv-dart.liga.nu/x", "file:///etc"):
            with pytest.raises(nuliga.NuligaError):
                nuliga.check_url(bad)

    def test_feed_link_from_the_team_page(self):
        with _serve(""):
            assert nuliga.feed_url_for(TEAM_PAGE) == FEED

    def test_page_without_calendar(self):
        with (
            mock.patch.object(nuliga, "_fetch", return_value="<html></html>"),
            pytest.raises(nuliga.NuligaError),
        ):
            nuliga.feed_url_for(TEAM_PAGE)


@pytest.mark.django_db
class TestSync:
    def test_first_import_creates_matchdays(self, link, captain_user):
        with _serve(_feed(HOME, AWAY)):
            result = nuliga.sync_link(link)
        assert result.first and len(result.created) == 2
        home = Matchday.objects.get(nuliga_uid="u1")
        assert (home.opponent, home.venue, home.start_time) == (
            "SV Gast",
            VenueChoice.HOME,
            time(14),
        )
        away = Matchday.objects.get(nuliga_uid="u2")
        assert (away.opponent, away.venue) == ("DC Heim", VenueChoice.AWAY)
        assert away.location.startswith("Halle (0902)")
        assert "Nr. 12" in away.description or "no. 12" in away.description
        link.refresh_from_db()
        assert link.nuliga_name == "Bullseye 1" and link.feed_url == FEED and not link.last_error
        # The captain hears about the import once.
        from notifications.models import Notification

        assert Notification.objects.filter(recipient=captain_user).count() == 1

    def test_changes_are_followed_and_reported(self, link, captain_user):
        with _serve(_feed(HOME, AWAY)):
            nuliga.sync_link(link)
        mail.outbox.clear()
        moved = HOME.replace("20270109T140000", "20270110T150000")
        with _serve(_feed(moved)):  # AWAY left the schedule
            result = nuliga.sync_link(link)
        md = Matchday.objects.get(nuliga_uid="u1")
        assert md.date == date(2027, 1, 10) and md.start_time == time(15)
        assert len(result.changed) == 1 and "10.01.2027 15:00" in result.changed[0][1][0]
        gone = Matchday.objects.get(nuliga_uid="u2")
        assert gone.nuliga_removed  # kept, only marked
        assert len(mail.outbox) == 1 and captain_user.email in mail.outbox[0].to
        assert "10.01.2027" in mail.outbox[0].body

    def test_nothing_changed_sends_nothing(self, link, captain_user):
        with _serve(_feed(HOME)):
            nuliga.sync_link(link)
            mail.outbox.clear()
            result = nuliga.sync_link(link)
        assert not result.anything and len(mail.outbox) == 0

    def test_a_matchday_entered_by_hand_is_linked(self, link, season, team):
        manual = Matchday.objects.create(
            team=team, season=season, opponent="Gast", date=date(2027, 1, 9)
        )
        with _serve(_feed(HOME)):
            result = nuliga.sync_link(link, notify=False)
        manual.refresh_from_db()
        assert result.adopted == [manual] and manual.nuliga_uid == "u1"
        assert manual.opponent == "SV Gast" and Matchday.objects.count() == 1

    def test_a_matchday_moved_before_the_import_is_linked(self, link, season, team):
        manual = Matchday.objects.create(
            team=team, season=season, opponent="SV Gast", date=date(2027, 2, 20)
        )
        other = Matchday.objects.create(
            team=team, season=season, opponent="SV Gast", date=date(2026, 9, 1), venue="away"
        )
        with _serve(_feed(HOME)):
            result = nuliga.sync_link(link, notify=False)
        manual.refresh_from_db()
        other.refresh_from_db()
        assert manual.nuliga_uid == "u1" and manual.date == date(2027, 1, 9)
        assert other.nuliga_uid == ""  # the home match fits better
        assert result.created == [] and "09.01.2027" in result.changed[0][1][0]
        assert any("09.01.2027" in line for line in nuliga.summary_lines(result))

    def test_error_is_stored(self, link):
        with (
            mock.patch.object(nuliga, "_fetch", side_effect=nuliga.NuligaError("down")),
            pytest.raises(nuliga.NuligaError),
        ):
            nuliga.sync_link(link)
        link.refresh_from_db()
        assert link.last_error == "down" and link.last_sync_at is not None


@pytest.mark.django_db
class TestDailyRun:
    def test_once_a_day_from_six(self, link):
        berlin = timezone.get_current_timezone()
        early = datetime(2026, 11, 26, 5, 30, tzinfo=berlin)
        later = datetime(2026, 11, 26, 6, 5, tzinfo=berlin)
        assert nuliga.links_due(early) == []
        assert nuliga.links_due(later) == [link]
        with _serve(_feed(HOME)):
            assert nuliga.sync_due(later) == 1
        assert nuliga.links_due(later) == []


@pytest.mark.django_db
class TestPages:
    def test_season_page_stores_the_link_and_imports(self, admin_client, season, team):
        url = reverse("season_update", args=[season.pk])
        props = inertia_props(admin_client.get(url))
        assert props["table"]["rows"][0]["fields"] == [f"nuliga_{team.pk}"]
        with _serve(_feed(HOME, AWAY)):
            admin_client.post(url, {"name": season.name, f"nuliga_{team.pk}": TEAM_PAGE})
        assert NuligaLink.objects.get().team_url == TEAM_PAGE
        assert Matchday.objects.filter(team=team).count() == 2

    def test_season_page_rejects_other_addresses(self, admin_client, season, team):
        url = reverse("season_update", args=[season.pk])
        admin_client.post(url, {"name": season.name, f"nuliga_{team.pk}": "https://example.org/x"})
        assert not NuligaLink.objects.exists()

    def test_sync_now_for_the_captain(self, captain_client, link):
        props = inertia_props(captain_client.get(reverse("matchdays:matchday_list")))
        assert props["nuliga"]["syncUrl"] == reverse("matchdays:nuliga_sync")
        with _serve(_feed(HOME)):
            resp = captain_client.post(reverse("matchdays:nuliga_sync"))
        assert resp.status_code == 302 and Matchday.objects.count() == 1

    def test_no_sync_for_other_teams_or_members(self, other_captain_client, player_client, link):
        assert other_captain_client.post(reverse("matchdays:nuliga_sync")).status_code == 403
        assert player_client.post(reverse("matchdays:nuliga_sync")).status_code == 403


@pytest.mark.django_db
def test_overview_next_matchdays(captain_client, season, team, other_team):
    from datetime import timedelta

    today = timezone.localdate()
    for team_obj, days in ((other_team, (2,)), (team, (3, 10, 20)), (other_team, (40,))):
        for d in days:
            Matchday.objects.create(
                team=team_obj, season=season, opponent=f"G{d}", date=today + timedelta(days=d)
            )
    Matchday.objects.create(
        team=team, season=season, opponent="past", date=today - timedelta(days=1)
    )
    rows = inertia_props(captain_client.get(reverse("overview")))["nextMatchdays"]
    assert [r["team"] for r in rows] == [team.name, other_team.name]  # own team first
    assert rows[0]["own"] and [m["opponent"] for m in rows[0]["matchdays"]] == ["G3", "G10"]
    assert [m["opponent"] for m in rows[1]["matchdays"]] == ["G2"]
    assert rows[0]["matchdays"][0]["url"] and rows[1]["matchdays"][0]["url"] is None


@pytest.mark.django_db
def test_overview_shows_the_next_one_beyond_two_weeks(player_client, season, team):
    from datetime import timedelta

    today = timezone.localdate()
    for d in (30, 45):
        Matchday.objects.create(
            team=team, season=season, opponent=f"G{d}", date=today + timedelta(days=d)
        )
    rows = inertia_props(player_client.get(reverse("overview")))["nextMatchdays"]
    assert [m["opponent"] for m in rows[0]["matchdays"]] == ["G30"]
    assert rows[0]["own"] is False and rows[0]["matchdays"][0]["url"] is None


@pytest.mark.django_db
def test_home_right_swapped_before_the_import(link, season, team):
    manual = Matchday.objects.create(
        team=team, season=season, opponent="SV Gast", date=date(2027, 2, 20), venue="away"
    )
    with _serve(_feed(HOME)):
        result = nuliga.sync_link(link, notify=False)
    manual.refresh_from_db()
    assert manual.nuliga_uid == "u1" and manual.venue == "home"
    changes = result.changed[0][1]
    assert any("09.01.2027" in c for c in changes) and len(changes) == 2


@pytest.mark.django_db
class TestManagedByHand:
    def _imported(self, link):
        with _serve(_feed(HOME)):
            nuliga.sync_link(link, notify=False)
        return Matchday.objects.get(nuliga_uid="u1")

    def test_hand_values_stay_and_a_nuliga_change_is_told_once(self, link, captain_user):
        md = self._imported(link)
        md.nuliga_manual = True
        md.start_time = time(19, 30)  # agreed with the opponent
        md.save()
        with _serve(_feed(HOME)):
            assert not nuliga.sync_link(link).anything  # nothing new in nuLiga
        md.refresh_from_db()
        assert md.start_time == time(19, 30)
        moved = HOME.replace("20270109T140000", "20270116T140000")
        with _serve(_feed(moved)):
            result = nuliga.sync_link(link)
            again = nuliga.sync_link(link)
        md.refresh_from_db()
        assert md.date == date(2027, 1, 9) and md.start_time == time(19, 30)
        assert len(result.noted) == 1 and "16.01.2027" in result.noted[0][1][0]
        lines = nuliga.summary_lines(result)
        assert any("managed by hand" in x or "von Hand" in x for x in lines)
        assert not again.anything  # told once, not every day

    def test_untick_follows_nuliga_again(self, link):
        md = self._imported(link)
        md.nuliga_manual, md.start_time = True, time(19, 30)
        md.save()
        md.nuliga_manual = False
        md.save()
        with _serve(_feed(HOME)):
            nuliga.sync_link(link, notify=False)
        md.refresh_from_db()
        assert md.start_time == time(14, 0)

    def test_edit_needs_the_tick(self, admin_client, link):
        md = self._imported(link)
        url = reverse("matchdays:matchday_update", args=[md.pk])
        data = {
            "team": md.team_id,
            "season": md.season_id,
            "opponent": md.opponent,
            "venue": md.venue,
            "date": "2027-01-08",
            "start_time": "19:30",
            "location": md.location,
            "description": md.description,
        }
        props = inertia_props(admin_client.post(url, data))
        assert "date" in props["errors"] and "start_time" in props["errors"]
        md.refresh_from_db()
        assert md.date == date(2027, 1, 9)
        resp = admin_client.post(url, {**data, "nuliga_manual": "on"})
        assert resp.status_code == 302
        md.refresh_from_db()
        assert md.nuliga_manual and md.date == date(2027, 1, 8) and md.start_time == time(19, 30)

    def test_hand_matchdays_have_no_tick(self, admin_client, season, team):
        md = Matchday.objects.create(team=team, season=season, opponent="X", date=date(2027, 1, 1))
        props = inertia_props(admin_client.get(reverse("matchdays:matchday_update", args=[md.pk])))
        assert "nuliga_manual" not in [f["name"] for f in props["fields"]]

    def test_deleted_matchday_is_not_imported_again(self, admin_client, link):
        md = self._imported(link)
        admin_client.post(reverse("matchdays:matchday_delete", args=[md.pk]))
        assert not Matchday.objects.exists()
        with _serve(_feed(HOME)):
            result = nuliga.sync_link(link, notify=False)
        assert not result.anything and not Matchday.objects.exists()


@pytest.mark.django_db
class TestCalendar:
    def test_feed_of_one_team(self, client, season, team, other_team):
        from app.matchdays.calendar import token_for

        today = timezone.localdate()
        Matchday.objects.create(
            team=team,
            season=season,
            opponent="SV Gast",
            date=today,
            start_time=time(19, 30),
            location="Halle, Weg 1",
            venue="home",
        )
        Matchday.objects.create(
            team=team, season=season, opponent="Weg", date=today, venue="away", nuliga_removed=True
        )
        Matchday.objects.create(team=other_team, season=season, opponent="Fremd", date=today)
        resp = client.get(reverse("matchdays:calendar", args=[token_for(team.pk)]))
        body = resp.content.decode()
        assert resp.status_code == 200 and resp["Content-Type"].startswith("text/calendar")
        assert body.count("BEGIN:VEVENT") == 2 and "Fremd" not in body
        assert f"SUMMARY:[H] {team.name} - SV Gast" in body
        assert f"SUMMARY:[A] Weg - {team.name}" in body
        assert r"LOCATION:Halle\, Weg 1" in body
        assert "Spielstart: 19:30" in body or "Match start: 19:30" in body
        assert "STATUS:CANCELLED" in body
        # Reminders 4 h and 90 min before - only for the match with a start time
        assert body.count("TRIGGER:-PT4H") == 1 and body.count("TRIGGER:-PT90M") == 1
        # 4 hours from 19:30 local time
        start = body.split("DTSTART:")[1][:16]
        end = body.split("DTEND:")[1][:16]
        assert int(end[9:11]) - int(start[9:11]) in (4, -20)

    def test_all_teams_and_bad_tokens(self, client, season, team, other_team):
        from app.matchdays.calendar import token_for

        Matchday.objects.create(
            team=other_team, season=season, opponent="Fremd", date=timezone.localdate()
        )
        body = client.get(reverse("matchdays:calendar", args=[token_for(None)])).content.decode()
        assert "Fremd" in body
        assert client.get(reverse("matchdays:calendar", args=["forged"])).status_code == 404

    def test_links_on_the_pages(self, captain_client, season, team, other_team):
        cals = inertia_props(captain_client.get(reverse("matchdays:matchday_list")))["calendars"]
        assert cals[0]["team"] == team.name and cals[0]["own"]
        assert cals[0]["webcal"].startswith("webcal://") and len(cals) == 3  # 2 teams + all
        overview = inertia_props(captain_client.get(reverse("overview")))
        assert overview["calendars"][0]["url"] == cals[0]["url"]


@pytest.mark.django_db
class TestRetries:
    def _fail(self, link):
        with (
            mock.patch.object(nuliga, "_fetch", side_effect=nuliga.NuligaError("down")),
            pytest.raises(nuliga.NuligaError),
        ):
            nuliga.sync_link(link)
        link.refresh_from_db()

    def test_hourly_retry_then_the_system_admin_hears_about_it(self, link):
        from django.contrib.auth import get_user_model
        from notifications.models import Notification

        system = get_user_model().objects.create_superuser(email="sys@example.com", password="pw")
        berlin = timezone.get_current_timezone()
        self._fail(link)
        assert link.failures == 1
        tried = timezone.localtime(link.last_sync_at)
        # Retried after an hour - even at night - not before.
        assert nuliga.links_due(tried + timedelta(minutes=30)) == []
        assert nuliga.links_due(tried + timedelta(minutes=61)) == [link]
        for _i in range(nuliga.MAX_RETRIES - 1):
            self._fail(link)
        assert link.failures == nuliga.MAX_RETRIES
        assert Notification.objects.filter(recipient=system).count() == 1
        assert any(system.email in m.to for m in mail.outbox)
        # Then back to once a day; one more failure tells nobody again.
        later = timezone.localtime(link.last_sync_at) + timedelta(hours=2)
        if later.date() == timezone.localtime(link.last_sync_at).date():
            assert nuliga.links_due(later) == []
        self._fail(link)
        assert Notification.objects.filter(recipient=system).count() == 1
        assert berlin  # time zone of the club

    def test_success_resets_the_counter(self, link):
        self._fail(link)
        with _serve(_feed(HOME)):
            nuliga.sync_link(link, notify=False)
        link.refresh_from_db()
        assert link.failures == 0 and link.last_error == ""

    def test_unexpected_errors_count_too(self, link):
        with (
            mock.patch.object(nuliga, "_fetch", side_effect=ValueError("odd")),
            pytest.raises(nuliga.NuligaError),
        ):
            nuliga.sync_link(link)
        link.refresh_from_db()
        assert link.failures == 1 and "odd" in link.last_error

    def test_sync_now_reports_the_result(self, captain_client, link):
        from app.core.models import AuditAction, AuditLog

        page = reverse("matchdays:matchday_list")
        with _serve(_feed(HOME, AWAY)):
            captain_client.post(reverse("matchdays:nuliga_sync"))
        report = inertia_props(captain_client.get(page))["nuligaReport"]
        assert report[0]["team"] == link.team.name and report[0]["checked"] == 2
        assert [i["kind"] for i in report[0]["items"]] == ["new", "new"]
        assert inertia_props(captain_client.get(page))["nuligaReport"] is None  # shown once
        # Every change lands in the audit log, by the person who synced.
        logs = AuditLog.objects.filter(action=AuditAction.MATCHDAY_CREATED)
        assert logs.count() == 2 and logs.first().metadata["source"] == "nuLiga"
        moved = HOME.replace("20270109T140000", "20270116T140000")
        with _serve(_feed(moved, AWAY)):
            captain_client.post(reverse("matchdays:nuliga_sync"))
        report = inertia_props(captain_client.get(page))["nuligaReport"]
        changed = [i for i in report[0]["items"] if i["kind"] == "changed"]
        assert len(changed) == 1 and "16.01.2027" in changed[0]["changes"][0]
        entry = AuditLog.objects.filter(action=AuditAction.MATCHDAY_UPDATED).latest("pk")
        assert "16.01.2027" in entry.metadata["changes"][0]

    def test_nothing_changed_still_reports(self, captain_client, link):
        with _serve(_feed(HOME)):
            captain_client.post(reverse("matchdays:nuliga_sync"))
            captain_client.get(reverse("matchdays:matchday_list"))
            captain_client.post(reverse("matchdays:nuliga_sync"))
        report = inertia_props(captain_client.get(reverse("matchdays:matchday_list")))
        assert report["nuligaReport"][0]["items"] == [] and report["nuligaReport"][0]["ok"]

    def test_failure_is_in_the_report(self, captain_client, link):
        with mock.patch.object(nuliga, "_fetch", side_effect=nuliga.NuligaError("down")):
            captain_client.post(reverse("matchdays:nuliga_sync"))
        report = inertia_props(captain_client.get(reverse("matchdays:matchday_list")))
        assert report["nuligaReport"][0] == {
            **report["nuligaReport"][0],
            "ok": False,
            "error": "down",
        }

    def test_error_tag_on_the_matchday_list(self, captain_client, link):
        self._fail(link)
        info = inertia_props(captain_client.get(reverse("matchdays:matchday_list")))["nuliga"]
        assert info["teams"][0]["retrying"] and not info["teams"][0]["gaveUp"]
