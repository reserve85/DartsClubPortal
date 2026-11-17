"""Player pictures: upload, permissions, serving, avatar map."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from app.players.models import Player
from tests.conftest import inertia_props


def _png(w=400, h=300):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(buf, "PNG")
    return SimpleUploadedFile("me.png", buf.getvalue(), content_type="image/png")


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.mark.django_db
def test_member_uploads_own_picture_and_it_is_served(player_client, player_user):
    me = Player.objects.create(name="Pia Pfeil")
    player_user.player_link = me
    player_user.save()
    resp = player_client.post(reverse("avatar_upload"), {"avatar": _png()})
    assert resp.status_code == 302
    me.refresh_from_db()
    assert me.avatar.endswith(".jpg")
    img = player_client.get(reverse("player_avatar", args=[me.avatar]))
    assert img.status_code == 200 and img["Content-Type"] == "image/jpeg"
    props = inertia_props(player_client.get(reverse("accounts:settings")))
    assert me.avatar in props["player"]["avatar"]
    player_client.post(reverse("avatar_upload"), {"remove": "1"})
    me.refresh_from_db()
    assert me.avatar == ""


@pytest.mark.django_db
def test_member_cannot_change_others(player_client, player_user):
    other = Player.objects.create(name="Otto")
    resp = player_client.post(reverse("avatar_upload"), {"player": other.pk, "avatar": _png()})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_changes_anyone_and_bad_files_are_rejected(admin_client):
    other = Player.objects.create(name="Otto")
    admin_client.post(reverse("avatar_upload"), {"player": other.pk, "avatar": _png()})
    other.refresh_from_db()
    assert other.avatar
    bad = SimpleUploadedFile("x.png", b"no image", content_type="image/png")
    admin_client.post(reverse("avatar_upload"), {"player": other.pk, "avatar": bad})
    assert Player.objects.get(pk=other.pk).avatar == other.avatar


@pytest.mark.django_db
def test_pictures_need_login(client):
    assert client.get(reverse("player_avatar", args=["x.jpg"])).status_code == 302


@pytest.mark.django_db
def test_every_admin_area_may_change_pictures(role_groups, captain_client):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from django.test import Client

    from app.core.permissions import GROUP_ADMIN

    user = get_user_model().objects.create_user(
        email="portal@example.com", password="pw", approval_status="approved", admin_portal=True
    )
    user.groups.add(Group.objects.get(name=GROUP_ADMIN))
    portal = Client()
    portal.force_login(user)
    target = Player.objects.create(name="Picture Target")
    portal.post(reverse("avatar_upload"), {"player": target.pk, "avatar": _png(512, 512)})
    target.refresh_from_db()
    assert target.avatar
    # a captain may not change somebody else's picture
    other = Player.objects.create(name="Not Mine")
    response = captain_client.post(reverse("avatar_upload"), {"player": other.pk, "avatar": _png()})
    assert response.status_code == 403


@pytest.mark.django_db
def test_cropped_square_stays_square(player_client, player_user, settings):
    """The browser sends the round crop as a 512 px square: stored as 256 px."""
    player_user.player_link = Player.objects.create(name="Square Me")
    player_user.save(update_fields=["player_link"])
    player_client.post(reverse("avatar_upload"), {"avatar": _png(512, 512)})
    player_user.player_link.refresh_from_db()
    path = settings.MEDIA_ROOT / "avatars" / player_user.player_link.avatar
    with Image.open(path) as img:
        assert img.size == (256, 256)


@pytest.mark.django_db
def test_member_page_offers_the_picture_to_admins(admin_client, captain_client, team):
    player = Player.objects.create(name="Pic Member", team=team)
    url = reverse("players:player_update", args=[player.pk])
    assert inertia_props(admin_client.get(url))["canPicture"] is True
    assert inertia_props(captain_client.get(url))["canPicture"] is False
