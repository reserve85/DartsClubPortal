"""Name and e-mail of an account.

* The linked player IS the person: the user list and the edit page show the
  player's name; the registration name only stands in for accounts without a
  player (club account, pending registrations).
* Members change their own login address under Settings: confirmation link to
  the new address, the old one stays valid until it is confirmed.
"""

import pytest
from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from app.core.permissions import GROUP_PLAYER
from app.players.models import Player
from tests.conftest import inertia_props

pytestmark = pytest.mark.django_db
User = get_user_model()


def _link(user, name="Max Muster"):
    user.player_link = Player.objects.create(name=name)
    user.save(update_fields=["player_link"])
    return user.player_link


# ---------------------------------------------------------------------------
# Name
# ---------------------------------------------------------------------------
def test_user_list_shows_the_player_name(admin_client, player_user):
    player_user.full_name = "Paulchen"
    player_user.save(update_fields=["full_name"])
    player = _link(player_user, "Paul Ludwig Beispiel")
    rows = inertia_props(admin_client.get(reverse("accounts:user_list")))["users"]
    row = next(r for r in rows if r["id"] == player_user.pk)
    assert row["name"] == "Paul Ludwig Beispiel"
    assert row["playerUrl"] == reverse("players:player_detail", args=[player.pk])


def test_user_list_falls_back_to_the_registration_name(admin_client, player_user):
    player_user.full_name = "Vereinskonto"
    player_user.save(update_fields=["full_name"])
    rows = inertia_props(admin_client.get(reverse("accounts:user_list")))["users"]
    row = next(r for r in rows if r["id"] == player_user.pk)
    assert row["name"] == "Vereinskonto" and row["playerUrl"] is None


def test_edit_page_header_uses_the_player_name(admin_client, player_user):
    player_user.full_name = "Paulchen"
    player_user.save(update_fields=["full_name"])
    _link(player_user)
    url = reverse("accounts:user_update", args=[player_user.pk])
    props = inertia_props(admin_client.get(url))
    assert props["badge"] == "Max Muster" and props["badgePerson"] is True
    assert props["subtitle"] == f"Max Muster · {player_user.email}"


def _update(client, user, **extra):
    data = {
        "email": user.email,
        "role": GROUP_PLAYER,
        "is_active": "on",
        "preferred_language": "de",
        **extra,
    }
    return client.post(reverse("accounts:user_update", args=[user.pk]), data)


def test_admin_sets_and_clears_the_registration_name(admin_client, player_user):
    response = admin_client.get(reverse("accounts:user_update", args=[player_user.pk]))
    assert "full_name" in response.context["form"].fields
    assert _update(admin_client, player_user, full_name="  Vereinskonto ").status_code == 302
    player_user.refresh_from_db()
    assert player_user.full_name == "Vereinskonto"
    assert _update(admin_client, player_user, full_name="").status_code == 302
    player_user.refresh_from_db()
    assert player_user.full_name == ""


def test_admin_create_form_offers_the_name(admin_client):
    response = admin_client.get(reverse("accounts:user_create"))
    assert "full_name" in response.context["form"].fields


SETTINGS = {
    "preferred_language": "de",
    "preferred_theme": "dark",
    "penalty_notify_mode": "immediate",
    "penalty_notify_time": "08:00",
    "repayment_notify": "False",
    "club_news_optin": "False",
}


def test_settings_name_only_without_player(captain_client, captain_user):
    props = inertia_props(captain_client.get(reverse("accounts:settings")))
    assert "full_name" in props["fields"]
    _link(captain_user)
    props = inertia_props(captain_client.get(reverse("accounts:settings")))
    assert "full_name" not in props["fields"]  # the player is the name


def test_user_without_player_changes_own_name(captain_client, captain_user):
    data = {**SETTINGS, "full_name": "Carla K."}
    assert captain_client.post(reverse("accounts:settings"), data).status_code == 302
    captain_user.refresh_from_db()
    assert captain_user.full_name == "Carla K."


def test_settings_without_name_keep_the_stored_one(captain_client, captain_user):
    captain_user.full_name = "Carla Captain"
    captain_user.save(update_fields=["full_name"])
    assert captain_client.post(reverse("accounts:settings"), SETTINGS).status_code == 302
    captain_user.refresh_from_db()
    assert captain_user.full_name == "Carla Captain"


# ---------------------------------------------------------------------------
# E-mail change
# ---------------------------------------------------------------------------
URL = reverse("accounts:settings_email")


def _ask(client, email="new@example.com", password="pw"):
    return client.post(URL, {"email": email, "password": password})


def test_settings_show_account_data(captain_client, captain_user):
    props = inertia_props(captain_client.get(reverse("accounts:settings")))
    assert props["email"] == captain_user.email
    assert props["pendingEmail"] == "" and props["emailUrl"] == URL


def test_change_sends_a_link_and_keeps_the_old_address(captain_client, captain_user):
    mail.outbox.clear()
    assert _ask(captain_client).status_code == 302
    captain_user.refresh_from_db()
    assert captain_user.email == "captain@example.com"  # unchanged until confirmed
    assert [m.to for m in mail.outbox] == [["new@example.com"]]
    props = inertia_props(captain_client.get(reverse("accounts:settings")))
    assert props["pendingEmail"] == "new@example.com"


def test_confirmation_link_switches_the_address(captain_client, captain_user):
    _ask(captain_client)
    address = EmailAddress.objects.get(email="new@example.com")
    key = EmailConfirmationHMAC(address).key
    response = captain_client.post(reverse("account_confirm_email", args=[key]))
    assert response.status_code == 302
    captain_user.refresh_from_db()
    assert captain_user.email == "new@example.com"
    emails = EmailAddress.objects.filter(user=captain_user).values_list("email", flat=True)
    assert list(emails) == ["new@example.com"]  # the old address is gone
    login = Client().post(reverse("account_login"), {"login": "new@example.com", "password": "pw"})
    assert login.status_code == 302


def test_wrong_password_changes_nothing(captain_client, captain_user):
    mail.outbox.clear()
    props = inertia_props(_ask(captain_client, password="wrong"))
    assert "password" in props["emailErrors"]
    assert not EmailAddress.objects.filter(email="new@example.com").exists()
    assert not mail.outbox


def test_address_of_someone_else_is_refused(captain_client, admin_user):
    props = inertia_props(_ask(captain_client, email="ADMIN@example.com"))
    assert "email" in props["emailErrors"]


def test_own_current_address_is_refused(captain_client):
    props = inertia_props(_ask(captain_client, email="captain@example.com"))
    assert "email" in props["emailErrors"]


def test_a_second_request_replaces_the_first(captain_client, captain_user):
    _ask(captain_client, email="first@example.com")
    _ask(captain_client, email="second@example.com")
    pending = EmailAddress.objects.filter(user=captain_user, verified=False)
    assert list(pending.values_list("email", flat=True)) == ["second@example.com"]


def test_change_can_be_withdrawn(captain_client, captain_user):
    _ask(captain_client)
    assert captain_client.post(URL, {"action": "cancel"}).status_code == 302
    assert not EmailAddress.objects.filter(email="new@example.com").exists()
    captain_user.refresh_from_db()
    assert captain_user.email == "captain@example.com"


@override_settings(ACCOUNT_EMAIL_VERIFICATION="none")
def test_without_verification_the_change_is_immediate(captain_client, captain_user):
    mail.outbox.clear()
    assert _ask(captain_client).status_code == 302
    captain_user.refresh_from_db()
    assert captain_user.email == "new@example.com"
    assert EmailAddress.objects.get(user=captain_user).verified
    assert not mail.outbox


def test_allauth_email_page_leads_to_settings(captain_client):
    response = captain_client.get("/accounts/email/")
    assert response.status_code == 302
    assert response["Location"].endswith("/accounts/settings/")


def test_anonymous_cannot_change_an_address():
    assert Client().post(URL, {"email": "x@example.com", "password": "pw"}).status_code == 302
    assert not EmailAddress.objects.filter(email="x@example.com").exists()
