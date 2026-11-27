"""The React app shell: menu per role, badges, language, theme, cookie notice.

Checked on the shared page data (app/core/inertia_share.py) that the shell
renders from.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from app.notifications.inapp import notify_user
from tests.conftest import inertia_props

pytestmark = pytest.mark.django_db
User = get_user_model()
PAGE = reverse("dashboard:financial_overview")


def _props(client, url=PAGE):
    resp = client.get(url)
    assert resp.status_code == 200
    return inertia_props(resp)


def _groups(props):
    return [g["key"] for g in props["nav"]]


def _hrefs(props, key):
    return [i["href"] for g in props["nav"] if g["key"] == key for i in g["items"]]


def test_menu_groups_per_role(admin_client, captain_client, player_client):
    # team management (matchdays, teams, catalog, cash box) lives in "penalty"
    assert _groups(_props(admin_client)) == ["elo", "penalty", "admin"]
    assert _groups(_props(captain_client)) == ["elo", "penalty"]
    assert _groups(_props(player_client)) == ["elo", "penalty"]
    player_penalty = _hrefs(_props(player_client), "penalty")
    assert reverse("matchdays:matchday_list") not in player_penalty


def test_admin_menu_contents(admin_client):
    admin = _hrefs(_props(admin_client), "admin")
    for name in (
        "accounts:user_list",
        "season_list",
        "audit_list",
        "data_transfer",  # Import & Export (the import is linked there)
        "elo:manage",
    ):
        assert reverse(name) in admin
    assert reverse("teams:team_list") in _hrefs(_props(admin_client), "penalty")


def test_captain_menu_has_team_tools_but_no_admin(captain_client):
    props = _props(captain_client)
    captain = _hrefs(props, "penalty")
    assert reverse("teams:cashier_list") in captain
    assert props["urls"]["schedule"] == reverse("schedule")  # matchdays: the schedule
    assert all(reverse("accounts:user_list") not in _hrefs(props, k) for k in _groups(props))
    assert props["auth"]["user"]["isCaptain"] is True and props["auth"]["user"]["isAdmin"] is False


def test_bell_badge_counts_for_every_account(
    admin_client, admin_user, captain_client, captain_user, player_client, player_user, role_groups
):
    for client, user in (
        (admin_client, admin_user),
        (captain_client, captain_user),
        (player_client, player_user),
    ):
        assert _props(client)["counts"]["notifications"] == 0
        notify_user(recipient=user, verb="Hello")
        assert _props(client)["counts"]["notifications"] == 1
    roleless = User.objects.create_user(
        email="none@example.com", password="pw", approval_status="approved"
    )
    c = Client()
    c.force_login(roleless)
    assert _props(c)["counts"]["notifications"] == 0


def test_pending_approval_badge_only_for_admins(admin_client, captain_client, pending_user):
    assert _props(admin_client)["counts"]["approvals"] == 1
    assert "approvals" not in _props(captain_client)["counts"]


def test_german_by_default_and_english_on_request(admin_client, admin_user):
    props = _props(admin_client)
    assert props["site"]["language"] == "de"
    assert props["i18n"]["Financial overview"] == "Finanzübersicht"
    assert props["i18n"]["Understood"] != "Understood"
    assert "Diese Website setzt nur notwendige Cookies" in " ".join(props["i18n"].values())
    admin_user.preferred_language = "en"
    admin_user.save()
    props = _props(admin_client, "/en" + PAGE)
    assert props["i18n"]["Financial overview"] == "Financial overview"


def test_theme_preference_is_applied_before_first_paint(admin_client, admin_user):
    admin_user.preferred_theme = "dark"
    admin_user.save()
    html = admin_client.get(PAGE).content.decode()
    assert 'var pref = "dark"' in html
    admin_client.cookies["dpm_theme"] = "light"  # the account choice wins over the cookie
    assert 'var pref = "dark"' in admin_client.get(PAGE).content.decode()


def test_club_logo_url_is_shared(admin_client):
    logo = _props(admin_client)["site"]["logo"]
    assert set(logo) == {"light", "dark"}


def test_messages_reach_the_page_as_toasts_once(admin_client):
    """A save message (Django messages) arrives in the shared ``flash`` prop."""
    resp = admin_client.post(reverse("season_create"), {"name": "2031/2032"})
    assert resp.status_code == 302
    flash = _props(admin_client, resp.url)["flash"]["messages"]
    assert len(flash) == 1 and flash[0]["level"] == "success"
    assert _props(admin_client, resp.url)["flash"]["messages"] == []  # shown only once
