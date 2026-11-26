"""Edits write what changed into the audit log ("Label: old → new")."""

from datetime import date

import pytest
from django.urls import reverse

from app.core.models import AuditAction, AuditLog
from app.matchdays.models import Matchday, Season


def _last(action):
    return AuditLog.objects.filter(action=action).latest("pk")


@pytest.mark.django_db
def test_matchday_edit_lists_the_changes(admin_client, team):
    season = Season.objects.create(name="2026/2027", is_default=True)
    md = Matchday.objects.create(
        team=team, season=season, opponent="SV Gast", date=date(2027, 1, 9)
    )
    admin_client.post(
        reverse("matchdays:matchday_update", args=[md.pk]),
        {
            "team": team.pk,
            "season": season.pk,
            "opponent": "SV Gast",
            "venue": "away",
            "date": "2027-01-10",
            "start_time": "19:30",
            "location": "",
            "description": "",
        },
    )
    changes = _last(AuditAction.MATCHDAY_UPDATED).metadata["changes"]
    assert any("09.01.2027 → 10.01.2027" in c for c in changes)
    assert any("– → 19:30" in c for c in changes)
    assert len(changes) == 3  # date, start time, venue - nothing else


@pytest.mark.django_db
def test_season_edit_lists_the_changes(admin_client, team):
    season = Season.objects.create(name="2026/2027")
    admin_client.post(
        reverse("season_update", args=[season.pk]),
        {"name": "2026/27", "is_default": "on", "teams": [team.pk]},
    )
    meta = _last(AuditAction.SEASON_UPDATED).metadata
    assert meta["name"] == "2026/27"
    assert any("2026/2027 → 2026/27" in c for c in meta["changes"])
    assert any(team.name in c for c in meta["changes"])


@pytest.mark.django_db
def test_own_settings_list_the_changes(player_client, player_user):
    from tests.conftest import inertia_props

    values = inertia_props(player_client.get(reverse("accounts:settings")))["values"]
    data = {k: v for k, v in values.items() if v is not None}
    data["start_page"] = "overview"
    for key, value in list(data.items()):
        if isinstance(value, bool):
            data[key] = "on" if value else ""
    player_client.post(reverse("accounts:settings"), data)
    changes = _last(AuditAction.USER_UPDATED).metadata["settings"]
    assert len(changes) == 1 and "→" in changes[0]
