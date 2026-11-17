"""Admin areas: Elo / Penalty / Portal admin, the system account, legacy admins."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from app.core.permissions import GROUP_ADMIN, user_admin_scopes
from tests.conftest import inertia_props

pytestmark = pytest.mark.django_db
User = get_user_model()

ELO_PAGES = ["elo:manage"]
PENALTY_PAGES = ["season_list", "teams:team_list", "matchdays:matchday_list", "teams:cashier_list"]
PORTAL_PAGES = ["accounts:user_list", "audit_list", "importer:import", "club_logo_admin"]


def _admin(role_groups, email, **areas):
    user = User.objects.create_user(email=email, password="pw", approval_status="approved", **areas)
    user.groups.add(Group.objects.get(name=GROUP_ADMIN))
    client = Client()
    client.force_login(user)
    return user, client


def _status(client, names):
    return {name: client.get(reverse(name)).status_code for name in names}


def _admin_menu(client):
    props = inertia_props(client.get(reverse("rights")))
    return [i["href"] for g in props["nav"] if g["key"] == "admin" for i in g["items"]]


@pytest.mark.parametrize(
    ("areas", "allowed", "refused"),
    [
        ({"admin_elo": True}, ELO_PAGES, PENALTY_PAGES + PORTAL_PAGES),
        ({"admin_penalty": True}, PENALTY_PAGES, ELO_PAGES + PORTAL_PAGES),
        ({"admin_portal": True}, PORTAL_PAGES, ELO_PAGES + PENALTY_PAGES),
        ({"admin_elo": True, "admin_penalty": True}, ELO_PAGES + PENALTY_PAGES, PORTAL_PAGES),
    ],
)
def test_each_area_opens_exactly_its_pages(role_groups, areas, allowed, refused):
    _user, client = _admin(role_groups, "area@example.com", **areas)
    assert set(_status(client, allowed).values()) == {200}, _status(client, allowed)
    assert set(_status(client, refused).values()) == {403}, _status(client, refused)


def test_admin_from_before_the_areas_keeps_everything(role_groups):
    user, client = _admin(role_groups, "legacy@example.com")  # group only, no flags
    assert user_admin_scopes(user) == {"elo", "penalty", "portal"}
    assert set(_status(client, ELO_PAGES + PENALTY_PAGES + PORTAL_PAGES).values()) == {200}


def test_system_account_always_has_every_area(db):
    system = User.objects.create_superuser(email="system@example.com", password="pw")
    assert user_admin_scopes(system) == {"elo", "penalty", "portal"}
    client = Client()
    client.force_login(system)
    assert set(_status(client, ELO_PAGES + PENALTY_PAGES + PORTAL_PAGES).values()) == {200}


def test_system_account_cannot_be_demoted_by_another_admin(role_groups):
    system = User.objects.create_superuser(email="system@example.com", password="pw")
    _portal, client = _admin(role_groups, "portal@example.com", admin_portal=True)
    fields = {
        f["name"]: f
        for f in inertia_props(client.get(reverse("accounts:user_update", args=[system.pk])))[
            "fields"
        ]
    }
    assert all(
        fields[n]["disabled"]
        for n in ("role", "is_active", "admin_elo", "admin_penalty", "admin_portal")
    )
    client.post(
        reverse("accounts:user_update", args=[system.pk]),
        {"email": system.email, "role": "Player", "is_active": "", "preferred_language": "de"},
    )
    system.refresh_from_db()
    assert (
        system.is_superuser
        and system.is_active
        and user_admin_scopes(system) == {"elo", "penalty", "portal"}
    )


def test_menu_shows_only_the_own_areas(role_groups):
    _u, elo = _admin(role_groups, "elo@example.com", admin_elo=True)
    _u, pen = _admin(role_groups, "pen@example.com", admin_penalty=True)
    _u, por = _admin(role_groups, "por@example.com", admin_portal=True)
    members = reverse("players:player_list")  # every admin area manages members
    assert _admin_menu(elo) == [members, reverse("elo:manage")]
    assert _admin_menu(pen) == [members, reverse("season_list")]
    assert reverse("accounts:user_list") in _admin_menu(por) and reverse(
        "elo:manage"
    ) not in _admin_menu(por)


def test_user_form_stores_the_areas(admin_client, role_groups):
    target = User.objects.create_user(
        email="t@example.com", password="pw", approval_status="approved"
    )
    url = reverse("accounts:user_update", args=[target.pk])
    base = {
        "email": target.email,
        "is_active": "on",
        "preferred_language": "de",
        "elo_access": "on",
        "penalty_access": "on",
    }
    admin_client.post(url, {**base, "role": GROUP_ADMIN, "admin_elo": "on"})
    target.refresh_from_db()
    assert user_admin_scopes(target) == {"elo"}
    admin_client.post(url, {**base, "role": GROUP_ADMIN})  # admin without a tick = everything
    target.refresh_from_db()
    assert user_admin_scopes(target) == {"elo", "penalty", "portal"}
    admin_client.post(
        url, {**base, "role": "Player", "admin_portal": "on"}
    )  # user role clears areas
    target.refresh_from_db()
    assert user_admin_scopes(target) == set() and not target.admin_portal


def test_last_portal_admin_cannot_drop_the_portal_area(role_groups):
    me, client = _admin(role_groups, "only@example.com", admin_portal=True, admin_elo=True)
    client.post(
        reverse("accounts:user_update", args=[me.pk]),
        {
            "email": me.email,
            "role": GROUP_ADMIN,
            "admin_elo": "on",
            "is_active": "on",
            "preferred_language": "de",
        },
    )
    me.refresh_from_db()
    assert me.admin_portal  # refused: nobody could manage users any more


def test_area_admin_sees_the_own_module_even_without_module_access(role_groups):
    _u, client = _admin(role_groups, "elo2@example.com", admin_elo=True, elo_access=False)
    assert client.get(reverse("elo:ranking")).status_code == 200


def test_approval_bell_goes_to_portal_admins_only(role_groups):
    from app.notifications.inapp import admin_recipients

    elo, _c = _admin(role_groups, "elo3@example.com", admin_elo=True)
    portal, _c = _admin(role_groups, "portal3@example.com", admin_portal=True)
    recipients = admin_recipients()
    assert portal in recipients and elo not in recipients


def test_rights_page_reports_the_areas(role_groups):
    _u, client = _admin(role_groups, "pen4@example.com", admin_penalty=True)
    assert inertia_props(client.get(reverse("rights")))["me"]["adminScopes"] == ["penalty"]
