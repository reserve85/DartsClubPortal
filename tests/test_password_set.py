"""Portal admins set a password for another account; the club account has no self-service."""

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client
from django.urls import reverse

from app.core.models import AuditAction, AuditLog
from app.core.permissions import GROUP_ADMIN
from tests.conftest import inertia_props

User = get_user_model()
NEW = "Neues-Vereins-Passwort-2026"


def _client(user):
    client = Client()
    client.force_login(user)
    return client


def _url(user):
    return reverse("accounts:user_set_password", args=[user.pk])


@pytest.fixture
def club_user(db):
    return User.objects.create_user(
        email="tablet@example.com",
        password="old-club-pw",
        approval_status="approved",
        is_club_account=True,
    )


@pytest.fixture
def portal_admin(role_groups):
    user = User.objects.create_user(
        email="portal@example.com", password="pw", approval_status="approved", admin_portal=True
    )
    user.groups.add(role_groups[GROUP_ADMIN])
    return user


class TestSetPassword:
    def test_portal_admin_sets_a_password(self, portal_admin, player_user):
        member = _client(player_user)
        resp = _client(portal_admin).post(_url(player_user), {"password1": NEW, "password2": NEW})
        assert resp.status_code == 302
        player_user.refresh_from_db()
        assert player_user.check_password(NEW)
        entry = AuditLog.objects.filter(action=AuditAction.USER_UPDATED).latest("pk")
        assert entry.metadata == {"password": "set by an admin"}
        # The member's old session ends with the new password.
        assert member.get(reverse("accounts:settings")).status_code == 302

    def test_club_account_password(self, portal_admin, club_user):
        _client(portal_admin).post(_url(club_user), {"password1": NEW, "password2": NEW})
        club_user.refresh_from_db()
        assert club_user.check_password(NEW)

    @pytest.mark.parametrize(
        "data",
        [
            {"password1": NEW, "password2": NEW + "x"},
            {"password1": "12345678", "password2": "12345678"},
        ],
    )
    def test_mismatch_or_weak_password_changes_nothing(self, portal_admin, player_user, data):
        _client(portal_admin).post(_url(player_user), data)
        player_user.refresh_from_db()
        assert player_user.check_password("pw")

    @pytest.mark.parametrize("area", ["admin_elo", "admin_penalty"])
    def test_other_admin_areas_may_not(self, role_groups, player_user, area):
        admin = User.objects.create_user(
            email="area@example.com", password="pw", approval_status="approved", **{area: True}
        )
        admin.groups.add(role_groups[GROUP_ADMIN])
        resp = _client(admin).post(_url(player_user), {"password1": NEW, "password2": NEW})
        assert resp.status_code == 403
        player_user.refresh_from_db()
        assert player_user.check_password("pw")

    def test_members_may_not(self, player_user, captain_user):
        resp = _client(captain_user).post(_url(player_user), {"password1": NEW, "password2": NEW})
        assert resp.status_code == 403
        assert _client(player_user).get(_url(captain_user)).status_code in (403, 405)

    def test_not_for_the_own_account_or_the_system_account(self, portal_admin):
        system = User.objects.create_superuser(email="system@example.com", password="pw")
        client = _client(portal_admin)
        for target in (portal_admin, system):
            client.post(_url(target), {"password1": NEW, "password2": NEW})
            target.refresh_from_db()
            assert target.check_password("pw")

    def test_edit_page_offers_the_card(self, portal_admin, player_user, club_user):
        client = _client(portal_admin)
        props = inertia_props(client.get(reverse("accounts:user_update", args=[club_user.pk])))
        assert props["passwordSet"] == {
            "url": _url(club_user),
            "name": club_user.email,
            "club": True,
        }
        own = inertia_props(client.get(reverse("accounts:user_update", args=[portal_admin.pk])))
        assert own["passwordSet"] is None


class TestClubAccountSelfService:
    def test_settings_show_no_password_or_email_change(self, club_user):
        props = inertia_props(_client(club_user).get(reverse("accounts:settings")))
        assert props["managed"] is True
        assert props["passwordUrl"] == "" and props["emailUrl"] == ""

    def test_password_change_is_locked(self, club_user):
        client = _client(club_user)
        resp = client.get(reverse("account_change_password"))
        assert resp.headers["Location"] == reverse("accounts:settings")
        client.post(
            reverse("account_change_password"),
            {"oldpassword": "old-club-pw", "password1": NEW, "password2": NEW},
        )
        club_user.refresh_from_db()
        assert club_user.check_password("old-club-pw")

    def test_email_change_is_locked(self, club_user):
        _client(club_user).post(
            reverse("accounts:settings_email"),
            {"email": "other@example.com", "password": "old-club-pw"},
        )
        club_user.refresh_from_db()
        assert club_user.email == "tablet@example.com"

    def test_forgot_password_skips_the_club_account(self, client, club_user, player_user):
        client.post(reverse("account_reset_password"), {"email": club_user.email})
        assert not any("/password/reset/key/" in m.body for m in mail.outbox)
        client.post(reverse("account_reset_password"), {"email": player_user.email})
        assert any("/password/reset/key/" in m.body for m in mail.outbox)

    def test_members_keep_their_self_service(self, player_user):
        props = inertia_props(_client(player_user).get(reverse("accounts:settings")))
        assert props["managed"] is False
        assert props["passwordUrl"] and props["emailUrl"]
        assert _client(player_user).get(reverse("account_change_password")).status_code == 200


def test_own_password_change_leads_back_to_settings(player_user):
    client = _client(player_user)
    resp = client.post(
        reverse("account_change_password"),
        {"oldpassword": "pw", "password1": NEW, "password2": NEW},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == reverse("accounts:settings")
    player_user.refresh_from_db()
    assert player_user.check_password(NEW)
