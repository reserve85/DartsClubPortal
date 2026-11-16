"""The "Who may do what?" page: reachable for every account, personal facts right."""

import pytest
from django.test import Client
from django.urls import reverse

from tests.conftest import inertia_props

pytestmark = pytest.mark.django_db
URL = reverse("rights")


def test_anonymous_is_sent_to_login():
    assert Client().get(URL).status_code == 302


def test_every_role_sees_the_page(admin_client, captain_client, player_client):
    for client in (admin_client, captain_client, player_client):
        assert client.get(URL).status_code == 200


def test_personal_facts(admin_client, captain_client, captain_user, player_client):
    assert inertia_props(admin_client.get(URL))["me"]["isAdmin"] is True
    captain = inertia_props(captain_client.get(URL))["me"]
    assert captain["isAdmin"] is False and captain["captainOf"] == captain_user.team.name
    player = inertia_props(player_client.get(URL))["me"]
    assert player["captainOf"] is None and player["cashierOf"] == []


def test_cashier_is_listed(admin_client, admin_user, team):
    from app.teams.services import set_cashier

    set_cashier(team=team, user=admin_user, actor=admin_user)
    assert inertia_props(admin_client.get(URL))["me"]["cashierOf"] == [team.name]


def test_user_menu_links_the_page(player_client):
    assert inertia_props(player_client.get(URL))["urls"]["rights"] == URL
