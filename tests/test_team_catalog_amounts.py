"""Team-specific catalog fees — override model, assignment, view permissions."""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from app.penalties.forms import PenaltyAssignForm
from app.penalties.models import PenaltyType, TeamCatalogAmount
from app.penalties.services import assign_group_penalty
from tests.conftest import inertia_props

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Model / effective amount
# ---------------------------------------------------------------------------
def test_amount_for_team_falls_back_to_default(catalog_normal, team, other_team):
    assert catalog_normal.amount_for_team(team) == Decimal(5)
    assert catalog_normal.amount_for_team(other_team) == Decimal(5)
    assert catalog_normal.amount_for_team(None) == Decimal(5)


def test_amount_for_team_uses_override_only_for_that_team(catalog_normal, team, other_team):
    TeamCatalogAmount.objects.create(team=team, catalog_item=catalog_normal, amount_eur=1)
    assert catalog_normal.amount_for_team(team) == Decimal(1)
    assert catalog_normal.amount_for_team(other_team) == Decimal(5)


def test_catalog_type_still_valid_choices(catalog_normal):
    assert catalog_normal.type == PenaltyType.NORMAL


# ---------------------------------------------------------------------------
# Assignment uses the effective team amount
# ---------------------------------------------------------------------------
def test_normal_assignment_uses_team_override_via_view(
    admin_client, matchday_with_players, catalog_normal, team
):
    TeamCatalogAmount.objects.create(team=team, catalog_item=catalog_normal, amount_eur=1)
    md, players = matchday_with_players(2)

    response = admin_client.post(
        reverse("penalties:penalty_create", args=[md.pk]),
        {"catalog_item": catalog_normal.pk, "player": players[0].pk},
    )
    assert response.status_code == 302
    penalty = md.penalties.get(player=players[0])
    assert penalty.amount_eur == Decimal(1)


def test_normal_assignment_uses_default_without_override(
    admin_client, matchday_with_players, catalog_normal
):
    md, players = matchday_with_players(2)
    response = admin_client.post(
        reverse("penalties:penalty_create", args=[md.pk]),
        {"catalog_item": catalog_normal.pk, "player": players[0].pk},
    )
    assert response.status_code == 302
    assert md.penalties.get(player=players[0]).amount_eur == Decimal(5)


def test_group_assignment_uses_team_override(
    matchday_with_players, catalog_group, admin_user, team
):
    TeamCatalogAmount.objects.create(team=team, catalog_item=catalog_group, amount_eur=2)
    md, players = matchday_with_players(3)

    created = assign_group_penalty(
        matchday=md, trigger_player=players[0], catalog_item=catalog_group, actor=admin_user
    )
    assert created
    assert all(row.amount_eur == Decimal(2) for row in created)


# ---------------------------------------------------------------------------
# Assignment dropdown — the option labels show the TEAM's own fee
# ---------------------------------------------------------------------------
def test_dropdown_label_shows_the_teams_own_fee(
    matchday_with_players, catalog_normal, team, other_team
):
    """The penalty-type dropdown used ``str(item)`` — the DEFAULT amount.

    Teams with their own override therefore SAW the first team's fee (the
    seed value kept on the catalog row) while the assignment charged their
    real one — the display-only bug of 10/2026.
    """
    TeamCatalogAmount.objects.create(team=team, catalog_item=catalog_normal, amount_eur=3)
    TeamCatalogAmount.objects.create(team=other_team, catalog_item=catalog_normal, amount_eur=1)
    md, _players = matchday_with_players(1)  # a matchday of the default ``team``

    field = PenaltyAssignForm(matchday=md).fields["catalog_item"]
    label = field.label_from_instance(catalog_normal)

    # The team's own fee — NOT the default amount str(item) would render …
    assert label == f"{catalog_normal.description} ({catalog_normal.amount_for_team(team)} €)"
    assert catalog_normal.amount_for_team(team) != catalog_normal.amount_eur
    assert label != str(catalog_normal)


def test_dropdown_label_falls_back_to_the_default_amount_without_a_matchday(catalog_normal):
    """System/fixture usage (no matchday) keeps the plain ``str(item)`` label."""
    field = PenaltyAssignForm().fields["catalog_item"]
    assert field.label_from_instance(catalog_normal) == str(catalog_normal)


def test_assign_page_renders_the_third_teams_fee_in_the_dropdown(
    admin_client, catalog_normal, team, other_team
):
    """The exact live scenario: THREE teams, distinct fees, third team's page.

    The rendered ``<option>`` of the third team must carry ITS fee (1.00 €)
    — never the first team's 5.00 €, while the posted assignment still
    charges the effective amount (covered above).
    """
    from app.matchdays.models import Matchday
    from app.teams.models import Team

    third = Team.objects.create(name="Wildboars 3")
    TeamCatalogAmount.objects.create(team=team, catalog_item=catalog_normal, amount_eur=5)
    TeamCatalogAmount.objects.create(team=other_team, catalog_item=catalog_normal, amount_eur=3)
    TeamCatalogAmount.objects.create(team=third, catalog_item=catalog_normal, amount_eur=1)
    md = Matchday.objects.create(
        team=third, opponent="SV Eichenberg", venue="home", date=date(2026, 9, 24)
    )

    props = inertia_props(admin_client.get(reverse("penalties:penalty_create", args=[md.pk])))
    item = next(i for i in props["items"] if i["description"] == "Late arrival")

    assert item["amount"] == float(catalog_normal.amount_for_team(third)) == 1.0  # team 3's fee


# ---------------------------------------------------------------------------
# Team fees + active flags — edited in the integrated catalog form
# (the dedicated fee page is gone; everything retargeted to catalog_update)
# ---------------------------------------------------------------------------
def test_admin_sees_all_teams_on_edit_form(admin_client, catalog_normal, team, other_team):
    response = admin_client.get(reverse("penalties:catalog_update", args=[catalog_normal.pk]))
    assert response.status_code == 200
    form = response.context["form"]
    for pk in (team.pk, other_team.pk):
        assert f"team_active_{pk}" in form.fields
        amount_field = form.fields[f"team_amount_{pk}"]
        assert amount_field.required  # every fee row must be filled
        assert amount_field.initial == catalog_normal.amount_eur  # prefilled default
    assert "apply_all" not in form.fields  # checkbox removed — JS auto-copies
    assert "active" not in form.fields  # the global switch is gone


def test_captain_edits_only_the_own_team(captain_client, catalog_normal, team, other_team):
    """Captains are no full admins: only their team's fee/flag is editable,
    the shared item fields (name, default fee, type) are read-only."""
    TeamCatalogAmount.objects.create(team=other_team, catalog_item=catalog_normal, amount_eur=4)
    url = reverse("penalties:catalog_update", args=[catalog_normal.pk])
    form = captain_client.get(url).context["form"]
    assert f"team_amount_{team.pk}" in form.fields
    assert f"team_amount_{other_team.pk}" not in form.fields
    assert form.fields["description"].disabled
    response = captain_client.post(
        url,
        {
            "description": "Hacked",
            "amount_eur": "99.00",
            "type": "NORMAL",
            f"team_active_{team.pk}": "on",
            f"team_amount_{team.pk}": "1",
            f"team_amount_{other_team.pk}": "3",
        },
    )
    assert response.status_code == 302
    catalog_normal.refresh_from_db()
    assert catalog_normal.description != "Hacked"
    assert TeamCatalogAmount.objects.get(catalog_item=catalog_normal, team=team).amount_eur == 1
    assert (
        TeamCatalogAmount.objects.get(catalog_item=catalog_normal, team=other_team).amount_eur == 4
    )


def test_captain_creates_item_active_only_for_the_own_team(captain_client, team, other_team):
    form = captain_client.get(reverse("penalties:catalog_create")).context["form"]
    assert form.fields[f"team_active_{team.pk}"].initial is True
    assert f"team_amount_{other_team.pk}" not in form.fields
    response = captain_client.post(
        reverse("penalties:catalog_create"),
        {
            "description": "Team special",
            "amount_eur": "2.00",
            "type": "NORMAL",
            f"team_active_{team.pk}": "on",
            f"team_amount_{team.pk}": "2",
        },
    )
    assert response.status_code == 302
    rows = {
        r.team_id: r
        for r in TeamCatalogAmount.objects.filter(catalog_item__description="Team special")
    }
    assert rows[team.pk].active and not rows[other_team.pk].active


def test_admin_create_form_defaults_all_teams_active(admin_client, team, other_team):
    """An admin's create form starts with every team active."""
    response = admin_client.get(reverse("penalties:catalog_create"))
    assert response.status_code == 200
    form = response.context["form"]
    assert form.fields[f"team_active_{team.pk}"].initial is True
    assert form.fields[f"team_active_{other_team.pk}"].initial is True


def test_blank_fee_is_rejected_and_row_unchanged(admin_client, catalog_normal, team):
    """No row may ever be blank — the save is blocked, the row stays intact."""
    TeamCatalogAmount.objects.create(team=team, catalog_item=catalog_normal, amount_eur=1)
    url = reverse("penalties:catalog_update", args=[catalog_normal.pk])
    response = admin_client.post(
        url,
        {
            "description": catalog_normal.description,
            "amount_eur": "5.00",
            "type": "NORMAL",
            f"team_active_{team.pk}": "on",
            f"team_amount_{team.pk}": "",  # blank -> required error
        },
    )
    assert response.status_code == 200  # re-rendered with an error
    row = TeamCatalogAmount.objects.get(catalog_item=catalog_normal, team=team)
    assert row.amount_eur == Decimal(1)  # unchanged
    assert catalog_normal.amount_for_team(team) == Decimal(1)


def test_invalid_amount_is_rejected(admin_client, catalog_normal, team):
    url = reverse("penalties:catalog_update", args=[catalog_normal.pk])
    response = admin_client.post(
        url,
        {
            "description": catalog_normal.description,
            "amount_eur": "5.00",
            "type": "NORMAL",
            f"team_active_{team.pk}": "on",
            f"team_amount_{team.pk}": "-2",
        },
    )
    assert response.status_code == 200  # re-rendered with error
    assert not TeamCatalogAmount.objects.filter(catalog_item=catalog_normal).exists()


def test_player_cannot_open_edit_form(player_client, catalog_normal):
    url = reverse("penalties:catalog_update", args=[catalog_normal.pk])
    assert player_client.get(url).status_code == 403
    assert (
        player_client.post(
            url,
            {"description": "Hacked", "amount_eur": "1.00", "type": "NORMAL"},
        ).status_code
        == 403
    )


def test_anonymous_redirected_from_edit_form(db, catalog_normal):
    from django.test import Client

    response = Client().get(reverse("penalties:catalog_update", args=[catalog_normal.pk]))
    assert response.status_code == 302
    assert "login" in response.url


def test_catalog_list_shows_team_fee_overrides(admin_client, catalog_normal, team, other_team):
    from tests.conftest import inertia_props

    TeamCatalogAmount.objects.create(team=team, catalog_item=catalog_normal, amount_eur=1)
    props = inertia_props(admin_client.get(reverse("penalties:catalog_list")))
    (item,) = [i for i in props["items"] if i["id"] == catalog_normal.pk]
    fees = {row["name"]: row["amount"] for row in item["teams"]}
    assert fees[team.name] == 1.0
    # EVERY team shows its real fee — no "Default"/"Standard" placeholder,
    # even for a team without an explicit row yet (legacy: default amount).
    assert fees[other_team.name] == 5.0
    # a single action per row — the dedicated fee page is gone
    assert item["editUrl"] == reverse("penalties:catalog_update", args=[catalog_normal.pk])
