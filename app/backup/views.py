"""Import & Export: backup, restore and exports of the portal data.

* Database export: a consistent copy of the live SQLite database (SQLite
  online backup API - safe while the portal is running).
* Full backup: a ZIP with the database plus the pictures (player avatars,
  club logo) that live next to it in ``MEDIA_ROOT``.
* CSV exports (Elo) are linked here too.

Database and backup are for Portal admins, the CSV exports for Elo admins.
"""

import io
import os
import sqlite3
import tempfile
import zipfile

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from inertia import render as inertia_render

from app.core.models import AuditAction
from app.core.modules import ELO, enabled_modules
from app.core.permissions import user_is_elo_admin, user_is_portal_admin
from app.core.services import log_action

MEDIA_FOLDERS = ("avatars", "branding")


def _stamp() -> str:
    return timezone.localtime().strftime("%Y%m%d-%H%M")


def database_bytes() -> bytes:
    """A consistent copy of the live database (also while others write)."""
    connection.ensure_connection()
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    try:
        target = sqlite3.connect(path)
        try:
            connection.connection.backup(target)
        finally:
            target.close()
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.remove(path)


def backup_zip_bytes() -> bytes:
    """Database + pictures (avatars, club logo) in one ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("db.sqlite3", database_bytes())
        for folder in MEDIA_FOLDERS:
            root = os.path.join(settings.MEDIA_ROOT, folder)
            if not os.path.isdir(root):
                continue
            for name in sorted(os.listdir(root)):
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    zf.write(path, f"media/{folder}/{name}")
    return buf.getvalue()


def _download(data: bytes, filename: str, content_type: str) -> HttpResponse:
    response = HttpResponse(data, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response


class DataTransferView(LoginRequiredMixin, View):
    """The Import & Export page."""

    def get(self, request):
        portal = user_is_portal_admin(request.user)
        elo = ELO in enabled_modules() and user_is_elo_admin(request.user)
        if not (portal or elo):
            raise PermissionDenied
        return inertia_render(
            request,
            "Admin/DataTransfer",
            props={
                "can": {"backup": portal, "csv": elo},
                "urls": {
                    "database": reverse("data_export_db"),
                    "backup": reverse("data_export_zip"),
                    "restore": reverse("data_restore"),
                    "csv": [
                        {"href": reverse("elo:export_ranking"), "label": "ranking"},
                        {"href": reverse("elo:export_matches"), "label": "matches"},
                        {"href": reverse("elo:export_players"), "label": "players"},
                    ]
                    if elo
                    else [],
                },
            },
        )


class DatabaseExportView(LoginRequiredMixin, View):
    """Download the live database as ``.sqlite3`` (Portal admins)."""

    def get(self, request):
        if not user_is_portal_admin(request.user):
            raise PermissionDenied
        data = database_bytes()
        log_action(AuditAction.DATA_EXPORTED, user=request.user, metadata={"kind": "database"})
        return _download(data, f"dartsclubportal-{_stamp()}.sqlite3", "application/vnd.sqlite3")


class BackupExportView(LoginRequiredMixin, View):
    """Download database + pictures + club logo as one ZIP (Portal admins)."""

    def get(self, request):
        if not user_is_portal_admin(request.user):
            raise PermissionDenied
        data = backup_zip_bytes()
        log_action(AuditAction.DATA_EXPORTED, user=request.user, metadata={"kind": "backup"})
        return _download(data, f"dartsclubportal-backup-{_stamp()}.zip", "application/zip")


# ---------------------------------------------------------------- restore
MAX_RESTORE = 500 * 1024 * 1024
KEEP_SAFETY_COPIES = 5
ADMIN_COUNT_SQL = (
    "select count(*) from accounts_user u where u.is_active and (u.is_superuser or exists ("
    "select 1 from accounts_user_groups ug join auth_group g on g.id = ug.group_id "
    "where ug.user_id = u.id and g.name = 'Admin'))"
)


class RestoreError(Exception):
    """The upload cannot be restored (the message is shown to the admin)."""


def _check_database(path: str) -> None:
    """A readable, intact database of this portal with at least one admin."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RestoreError(_("The database in the backup is damaged."))
            tables = {
                r[0] for r in con.execute("select name from sqlite_master where type='table'")
            }
            if not {"accounts_user", "django_migrations", "players_player"} <= tables:
                raise RestoreError(_("This is not a backup of this portal."))
            admins = con.execute(ADMIN_COUNT_SQL).fetchone()[0]
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        raise RestoreError(_("The file is not a readable database.")) from exc
    if not admins:
        raise RestoreError(_("The backup has no active admin - nobody could log in afterwards."))


def _read_upload(upload, workdir: str) -> tuple[str, dict | None]:
    """(path of the database, media files - None for a database-only upload)."""
    if upload.size > MAX_RESTORE:
        raise RestoreError(_("The file is too large."))
    name = (upload.name or "").lower()
    db_path = os.path.join(workdir, "restore.sqlite3")
    if name.endswith((".sqlite3", ".sqlite", ".db")):
        with open(db_path, "wb") as fh:
            fh.writelines(upload.chunks())
        return db_path, None
    if not name.endswith(".zip"):
        raise RestoreError(_("Choose a backup (.zip) or a database (.sqlite3)."))
    try:
        zf = zipfile.ZipFile(upload)
    except zipfile.BadZipFile as exc:
        raise RestoreError(_("The ZIP file is damaged.")) from exc
    media: dict[str, bytes] = {}
    with zf:
        names = zf.namelist()
        if "db.sqlite3" not in names:
            raise RestoreError(_("The ZIP file contains no db.sqlite3."))
        for entry in names:
            if entry == "db.sqlite3" or entry.endswith("/"):
                continue
            parts = entry.split("/")
            # Only media/<avatars|branding>/<file>: nothing outside, no "..".
            if (
                len(parts) != 3
                or parts[0] != "media"
                or parts[1] not in MEDIA_FOLDERS
                or parts[2] in ("", ".", "..")
                or parts[2] != os.path.basename(parts[2])
            ):
                raise RestoreError(_("Unexpected file in the backup: %(name)s") % {"name": entry})
            media[f"{parts[1]}/{parts[2]}"] = zf.read(entry)
        with open(db_path, "wb") as fh:
            fh.write(zf.read("db.sqlite3"))
    return db_path, media


def _safety_copy() -> str:
    """Save the current state before it is replaced; keep the newest copies."""
    folder = str(settings.BACKUP_DIR)
    os.makedirs(folder, exist_ok=True)
    name = f"before-restore-{timezone.localtime().strftime('%Y%m%d-%H%M%S')}.zip"
    with open(os.path.join(folder, name), "wb") as fh:
        fh.write(backup_zip_bytes())
    copies = sorted(
        f for f in os.listdir(folder) if f.startswith("before-restore-") and f.endswith(".zip")
    )
    for old in copies[:-KEEP_SAFETY_COPIES]:
        os.remove(os.path.join(folder, old))
    return name


def restore_backup(upload) -> dict:
    """Replace the live database (and the pictures, for a ZIP) with the upload.

    Everything is checked first, then a safety copy of the current state is
    taken. The database is copied in with the SQLite online backup API (no
    file swap under the running portal); an older backup is then migrated
    to the current schema.
    """
    from django.core.management import call_command

    with tempfile.TemporaryDirectory() as workdir:
        db_path, media = _read_upload(upload, workdir)
        _check_database(db_path)
        safety = _safety_copy()
        source = sqlite3.connect(db_path)
        try:
            connection.ensure_connection()
            source.backup(connection.connection)
        finally:
            source.close()
    call_command("migrate", interactive=False, verbosity=0)
    if media is not None:
        for folder in MEDIA_FOLDERS:
            root = os.path.join(settings.MEDIA_ROOT, folder)
            os.makedirs(root, exist_ok=True)
            for old in os.listdir(root):
                if os.path.isfile(os.path.join(root, old)):
                    os.remove(os.path.join(root, old))
        for rel, data in media.items():
            with open(os.path.join(settings.MEDIA_ROOT, rel), "wb") as fh:
                fh.write(data)
    return {"safety": safety, "pictures": None if media is None else len(media)}


class RestoreView(LoginRequiredMixin, View):
    """POST: restore a full backup or a database (Portal admins, with password)."""

    def post(self, request):
        from django.contrib import messages
        from django.contrib.auth import get_user_model, login, logout
        from django.shortcuts import redirect

        user = request.user
        if not user_is_portal_admin(user):
            raise PermissionDenied
        upload = request.FILES.get("backup")
        if upload is None:
            messages.error(request, _("Choose a backup (.zip) or a database (.sqlite3)."))
            return redirect("data_transfer")
        if str(request.POST.get("confirm")).lower() not in ("1", "true", "on"):
            messages.error(request, _("Please confirm that all current data is replaced."))
            return redirect("data_transfer")
        if not user.check_password(request.POST.get("password") or ""):
            messages.error(request, _("The password is not correct."))
            return redirect("data_transfer")
        email = user.email
        backend = getattr(user, "backend", None) or "django.contrib.auth.backends.ModelBackend"
        try:
            result = restore_backup(upload)
        except RestoreError as exc:
            messages.error(request, str(exc))
            return redirect("data_transfer")
        # The sessions came back with the backup: sign the admin in again.
        again = get_user_model().objects.filter(email__iexact=email, is_active=True).first()
        if again is None or not user_is_portal_admin(again):
            logout(request)
            return redirect("account_login")
        login(request, again, backend=backend)
        log_action(
            AuditAction.DATA_IMPORTED,
            user=again,
            metadata={
                "kind": "restore",
                "safety_copy": result["safety"],
                "pictures": result["pictures"],
            },
        )
        messages.success(
            request,
            _("Backup restored. The previous state was saved as %(name)s.")
            % {"name": result["safety"]},
        )
        return redirect("data_transfer")
