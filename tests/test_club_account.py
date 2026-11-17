"""Club accounts: the shared login of the club - the only accounts with a QR code."""

import importlib

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from app.core.permissions import GROUP_ADMIN, GROUP_PLAYER
from app.players.models import Player

pytestmark = pytest.mark.django_db
User = get_user_model()


def _edit(client, user, **extra):
    data = {
        "email": user.email,
        "role": GROUP_PLAYER,
        "is_active": "on",
        "preferred_language": "de",
        **extra,
    }
    return client.post(reverse("accounts:user_update", args=[user.pk]), data)


def test_admin_marks_an_account_as_club_account(admin_client, player_user):
    assert _edit(admin_client, player_user, is_club_account="on").status_code == 302
    player_user.refresh_from_db()
    assert player_user.is_club_account and player_user.role == "club"


def test_club_account_cannot_be_admin_or_a_person(admin_client, player_user):
    response = _edit(admin_client, player_user, is_club_account="on", role=GROUP_ADMIN)
    assert response.status_code == 200
    player = Player.objects.create(name="Some Person")
    response = _edit(admin_client, player_user, is_club_account="on", player_link=player.pk)
    assert response.status_code == 200
    player_user.refresh_from_db()
    assert not player_user.is_club_account


def test_migration_marks_existing_imported_club_logins(role_groups):
    migration = importlib.import_module("app.accounts.migrations.0011_club_account")
    club = User.objects.create_user(
        email="club@example.com", password="pw", legacy_username="Kneipe"
    )
    linked = User.objects.create_user(
        email="p@example.com",
        password="pw",
        legacy_username="Person",
        player_link=Player.objects.create(name="Linked Person"),
    )
    admin = User.objects.create_user(email="a@example.com", password="pw", legacy_username="Boss")
    admin.groups.add(Group.objects.get(name=GROUP_ADMIN))
    migration.mark_club_accounts(apps, None)
    for user in (club, linked, admin):
        user.refresh_from_db()
    assert club.is_club_account
    assert not linked.is_club_account and not admin.is_club_account
