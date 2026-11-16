"""Player pictures: upload, permissions, serving, avatar map."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from app.players.models import Player


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
    html = player_client.get(reverse("accounts:settings")).content.decode()
    assert "avatar-map" in html and me.avatar in html
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
