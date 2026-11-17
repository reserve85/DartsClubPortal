"""Import & Export: database / full backup download, CSV links, permissions."""

import io
import sqlite3
import zipfile

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from app.core.models import AuditAction, AuditLog
from app.core.permissions import GROUP_ADMIN
from tests.conftest import inertia_props

pytestmark = pytest.mark.django_db
User = get_user_model()
PAGE = reverse("data_transfer")
DB = reverse("data_export_db")
ZIP = reverse("data_export_zip")


def _admin(email, **areas):
    user = User.objects.create_user(email=email, password="pw", approval_status="approved", **areas)
    user.groups.add(Group.objects.get(name=GROUP_ADMIN))
    client = Client()
    client.force_login(user)
    return client


def test_page_shows_what_each_area_may_do(admin_client, role_groups, player_client):
    props = inertia_props(admin_client.get(PAGE))
    assert props["can"] == {"backup": True, "import": True, "csv": True}
    assert len(props["urls"]["csv"]) == 3
    elo = inertia_props(_admin("elo@example.com", admin_elo=True).get(PAGE))
    assert elo["can"] == {"backup": False, "import": False, "csv": True}
    assert _admin("pen@example.com", admin_penalty=True).get(PAGE).status_code == 403
    assert player_client.get(PAGE).status_code == 403


# Real commits like in production: a test transaction would block the
# SQLite online backup on the shared in-memory test database.
@pytest.mark.django_db(transaction=True)
def test_database_download_is_a_real_sqlite_copy(admin_client, tmp_path, admin_user):
    response = admin_client.get(DB)
    assert response.status_code == 200
    assert response["Content-Disposition"].startswith('attachment; filename="dartsclubportal-')
    assert response.content.startswith(b"SQLite format 3")
    path = tmp_path / "copy.sqlite3"
    path.write_bytes(response.content)
    con = sqlite3.connect(path)
    emails = [r[0] for r in con.execute("select email from accounts_user")]
    con.close()
    assert admin_user.email in emails
    assert AuditLog.objects.filter(action=AuditAction.DATA_EXPORTED).exists()


# Real commits like in production: a test transaction would block the
# SQLite online backup on the shared in-memory test database.
@pytest.mark.django_db(transaction=True)
def test_backup_zip_holds_database_pictures_and_logo(admin_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "avatars").mkdir()
    (tmp_path / "avatars" / "7-abc.jpg").write_bytes(b"jpg")
    (tmp_path / "branding").mkdir()
    (tmp_path / "branding" / "logo-light.png").write_bytes(b"png")
    response = admin_client.get(ZIP)
    assert response.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert {"db.sqlite3", "media/avatars/7-abc.jpg", "media/branding/logo-light.png"} <= set(names)


def test_only_portal_admins_download_data(role_groups, captain_client):
    elo = _admin("elo2@example.com", admin_elo=True)
    for url in (DB, ZIP):
        assert elo.get(url).status_code == 403
        assert captain_client.get(url).status_code == 403
        assert Client().get(url).status_code == 302  # login first


def test_menu_has_import_and_export(admin_client, role_groups):
    def admin_menu(client):
        nav = inertia_props(client.get(reverse("rights")))["nav"]
        return [i["href"] for g in nav if g["key"] == "admin" for i in g["items"]]

    assert PAGE in admin_menu(admin_client)
    assert PAGE in admin_menu(_admin("elo3@example.com", admin_elo=True))
    assert PAGE not in admin_menu(_admin("pen3@example.com", admin_penalty=True))


# ---------------------------------------------------------------- restore
RESTORE = reverse("data_restore")


def _upload(name, data):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, data, content_type="application/octet-stream")


@pytest.fixture
def _dirs(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.BACKUP_DIR = tmp_path / "backups"
    (tmp_path / "media" / "avatars").mkdir(parents=True)
    return tmp_path


@pytest.mark.django_db(transaction=True)
def test_backup_round_trip(admin_client, _dirs):
    from app.players.models import Player

    Player.objects.create(name="Before Backup")
    (_dirs / "media" / "avatars" / "old.jpg").write_bytes(b"old")
    backup = admin_client.get(ZIP).content
    # changes after the backup ...
    Player.objects.filter(name="Before Backup").delete()
    Player.objects.create(name="After Backup")
    (_dirs / "media" / "avatars" / "old.jpg").unlink()
    (_dirs / "media" / "avatars" / "new.jpg").write_bytes(b"new")
    response = admin_client.post(
        RESTORE, {"backup": _upload("backup.zip", backup), "password": "pw", "confirm": "1"}
    )
    assert response.status_code == 302 and response["Location"] == PAGE
    # ... are gone, the backup is back
    assert Player.objects.filter(name="Before Backup").exists()
    assert not Player.objects.filter(name="After Backup").exists()
    assert sorted(p.name for p in (_dirs / "media" / "avatars").iterdir()) == ["old.jpg"]
    # a safety copy of the replaced state exists, the admin is still signed in
    assert [p.name.startswith("before-restore-") for p in (_dirs / "backups").iterdir()] == [True]
    assert admin_client.get(PAGE).status_code == 200
    assert AuditLog.objects.filter(
        action=AuditAction.DATA_IMPORTED, metadata__kind="restore"
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_database_only_restore_keeps_the_pictures(admin_client, _dirs):
    from app.players.models import Player

    Player.objects.create(name="In Database")
    database = admin_client.get(DB).content
    Player.objects.create(name="Later")
    (_dirs / "media" / "avatars" / "keep.jpg").write_bytes(b"keep")
    admin_client.post(
        RESTORE, {"backup": _upload("db.sqlite3", database), "password": "pw", "confirm": "1"}
    )
    assert not Player.objects.filter(name="Later").exists()
    assert (_dirs / "media" / "avatars" / "keep.jpg").exists()


@pytest.mark.django_db(transaction=True)
def test_nothing_happens_without_password_or_confirmation(admin_client, _dirs):
    from app.players.models import Player

    backup = admin_client.get(ZIP).content
    Player.objects.create(name="Still Here")
    for data in (
        {"backup": _upload("b.zip", backup), "password": "wrong", "confirm": "1"},
        {"backup": _upload("b.zip", backup), "password": "pw"},
    ):
        admin_client.post(RESTORE, data)
    assert Player.objects.filter(name="Still Here").exists()
    assert not (_dirs / "backups").exists()


@pytest.mark.django_db(transaction=True)
def test_bad_files_are_refused(admin_client, _dirs):
    from app.players.models import Player

    Player.objects.create(name="Untouched")
    database = admin_client.get(DB).content
    evil = io.BytesIO()
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("db.sqlite3", database)
        zf.writestr("media/avatars/../../evil.txt", b"x")
    for upload in (
        _upload("broken.zip", b"not a zip"),
        _upload("evil.zip", evil.getvalue()),
        _upload("db.sqlite3", b"SQLite format 3\x00garbage"),
        _upload("notes.txt", b"hello"),
    ):
        admin_client.post(RESTORE, {"backup": upload, "password": "pw", "confirm": "1"})
    assert Player.objects.filter(name="Untouched").exists()
    assert not (_dirs.parent / "evil.txt").exists()
    assert not (_dirs / "backups").exists()


def test_only_portal_admins_restore(role_groups, captain_client):
    elo = _admin("elo4@example.com", admin_elo=True)
    for client in (elo, captain_client):
        assert client.post(RESTORE, {"password": "pw", "confirm": "1"}).status_code == 403
