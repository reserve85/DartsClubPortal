"""Financial overview (React page): the rules formerly checked in the HTML,
now checked on the page data the page renders from."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from app.matchdays.models import Matchday, Season
from app.penalties.models import TeamCatalogAmount
from app.penalties.services import assign_penalty, record_payment
from tests.conftest import inertia_props

pytestmark = pytest.mark.django_db
User = get_user_model()
URL = reverse("dashboard:financial_overview")


def _fin(client, **params):
    resp = client.get(URL, params)
    assert resp.status_code == 200
    return inertia_props(resp)


def _penalty(md, player, item, actor, amount=None, text="Late arrival"):
    kw = {"amount_eur": amount} if amount is not None else {}
    return assign_penalty(
        matchday=md, player=player, catalog_item=item, description_snapshot=text, actor=actor, **kw
    )


def test_cashier_gets_payment_actions_others_read_only(
    admin_client,
    cashier,
    captain_client,
    player_client,
    matchday_with_players,
    catalog_normal,
    admin_user,
):
    md, players = matchday_with_players(2)
    _penalty(md, players[0], catalog_normal, admin_user, amount=5)
    team = _fin(admin_client)["team"]
    assert team["isCashier"] is True and team["cashier"] in (admin_user.full_name, admin_user.email)
    for client in (captain_client, player_client):
        other = _fin(client)["team"]
        assert other["isCashier"] is False
        assert other["cashier"] == team["cashier"]  # the cashier line is shown to every role


def test_no_cashier_hint_and_link_for_managers(admin_client, team):
    team = _fin(admin_client)["team"]
    assert team["cashier"] is None and team["canManage"] is True and team["isCashier"] is False


def test_assigned_and_most_common_penalties(
    admin_client, matchday_with_players, catalog_normal, admin_user
):
    md, players = matchday_with_players(2)
    _penalty(md, players[0], catalog_normal, admin_user, text="9 Punkte")
    _penalty(md, players[1], catalog_normal, admin_user)
    team = _fin(admin_client)["team"]
    assert any(
        "Late arrival" in p["description"] and "9 Punkte" in p["description"]
        for p in team["penalties"]
    )
    assert [r["description"] for r in team["mostCommon"]] == ["Late arrival"]
    assert team["mostCommon"][0]["count"] == 2


def test_captain_marking(admin_client, team, captain_user, player):
    captain_user.player_link = player
    captain_user.save()
    props = _fin(admin_client, team=team.pk)
    assert props["team"]["captains"] == [captain_user.full_name or captain_user.email]
    row = next(r for r in props["team"]["balances"] if r["playerId"] == player.pk)
    assert row["isCaptain"] is True and row["isCashier"] is False
    assert [t["name"] for t in props["teams"]] == sorted(
        t["name"] for t in props["teams"]
    )  # plain names


def test_admin_assigned_as_captain_is_listed(admin_client, admin_user, team):
    admin_user.team = team
    admin_user.save()
    assert _fin(admin_client, team=team.pk)["team"]["captains"] == [
        admin_user.full_name or admin_user.email
    ]


def test_inactive_captain_is_not_listed(admin_client, team, captain_user):
    captain_user.is_active = False
    captain_user.save()
    assert _fin(admin_client, team=team.pk)["team"]["captains"] == []


def test_captain_and_cashier_flags_on_one_row(admin_client, team, captain_user, player, admin_user):
    from app.teams.services import set_cashier

    captain_user.player_link = player
    captain_user.save()
    set_cashier(team=team, user=captain_user, actor=admin_user)
    row = next(
        r
        for r in _fin(admin_client, team=team.pk)["team"]["balances"]
        if r["playerId"] == player.pk
    )
    assert row["isCaptain"] is True and row["isCashier"] is True


def test_cashier_row_without_captaincy(admin_client, team, player, admin_user, role_groups):
    from app.teams.services import set_cashier

    plain = User.objects.create_user(
        email="cash@example.com", password="pw", approval_status="approved", player_link=player
    )
    plain.groups.add(role_groups["Player"])
    set_cashier(team=team, user=plain, actor=admin_user)
    row = next(
        r
        for r in _fin(admin_client, team=team.pk)["team"]["balances"]
        if r["playerId"] == player.pk
    )
    assert row["isCashier"] is True and row["isCaptain"] is False


def test_matchdays_today_and_past(admin_client, team):
    today = timezone.localdate()
    Matchday.objects.create(team=team, date=today, opponent="Today FC")
    Matchday.objects.create(team=team, date=today - timedelta(days=7), opponent="Past FC")
    rows = {
        m["label"].split(" - ")[-1] if "Today FC" not in m["label"] else "Today FC": m
        for m in _fin(admin_client, team=team.pk)["team"]["matchdays"]
    }
    today_row = next(m for m in rows.values() if "Today FC" in m["label"])
    past_row = next(m for m in rows.values() if "Past FC" in m["label"])
    assert today_row["isToday"] and not today_row["isPast"]
    assert past_row["isPast"] and not past_row["isToday"]


def test_price_list_for_every_role_with_team_fee_and_manual_flag(
    player_client, admin_client, team, catalog_normal, catalog_manual
):
    assert (
        player_client.get(reverse("penalties:catalog_list")).status_code == 403
    )  # management stays closed
    catalog = _fin(player_client)["team"]["catalog"]
    assert {c["description"] for c in catalog} == {"Late arrival", "Manual"}
    assert any(c["manual"] for c in catalog)
    TeamCatalogAmount.objects.update_or_create(
        team=team, catalog_item=catalog_normal, defaults={"amount_eur": Decimal(1), "active": True}
    )
    TeamCatalogAmount.objects.update_or_create(
        team=team, catalog_item=catalog_manual, defaults={"amount_eur": Decimal(2), "active": False}
    )
    catalog = _fin(admin_client, team=team.pk)["team"]["catalog"]
    assert catalog == [{"description": "Late arrival", "amount": 1.0, "manual": False}]


def test_inactive_players_with_open_amounts(
    admin_client, matchday_with_players, catalog_normal, admin_user
):
    md, players = matchday_with_players(2)
    _penalty(md, players[1], catalog_normal, admin_user, amount=5)
    players[1].active = False
    players[1].save()
    inactive = _fin(admin_client)["team"]["inactive"]
    assert [(r["name"], r["balance"]) for r in inactive] == [(players[1].name, 5.0)]


def test_payments_listed_and_credit_rows(
    admin_client, cashier, team, matchday_with_players, catalog_normal, admin_user
):
    md, players = matchday_with_players(2)
    _penalty(md, players[0], catalog_normal, admin_user, amount=5)
    record_payment(player=players[0], team=team, amount_eur=Decimal(8), actor=admin_user)
    team_props = _fin(admin_client)["team"]
    pay = team_props["payments"][0]
    assert pay["player"] == players[0].name and pay["amount"] == 8.0 and pay["receivedBy"]
    row = next(r for r in team_props["balances"] if r["playerId"] == players[0].pk)
    assert row["balance"] == -3.0  # credit -> the cashier gets "Pay out"


def test_season_picker_and_default(admin_client, team):
    Season.objects.all().update(is_default=False)
    old = Season.objects.create(name="2020/2021", is_default=True)
    props = _fin(admin_client)
    assert any(s["id"] == old.pk and s["isDefault"] for s in props["seasons"])
    resp = admin_client.post(reverse("season_set"), {"season": old.pk, "next": URL})
    assert resp.status_code == 302
    assert _fin(admin_client)["seasonId"] == old.pk


def test_roleless_account_reads_everything(db, team, role_groups):
    user = User.objects.create_user(
        email="nobody@example.com", password="pw", approval_status="approved"
    )
    c = Client()
    c.force_login(user)
    props = _fin(c)
    assert props["team"]["canManage"] is False and props["team"]["isCashier"] is False
