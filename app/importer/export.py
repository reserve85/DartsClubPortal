"""Import & Export: one page for the data of the portal.

* Database export: a consistent copy of the live SQLite database (SQLite
  online backup API - safe while the portal is running).
* Full backup: a ZIP with the database plus the pictures (player avatars,
  club logo) that live next to it in ``MEDIA_ROOT``.
* CSV exports (Elo) and the import of the old systems are linked here too.

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
                "can": {"backup": portal, "import": portal, "csv": elo},
                "urls": {
                    "database": reverse("data_export_db"),
                    "backup": reverse("data_export_zip"),
                    "import": reverse("importer:import"),
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
