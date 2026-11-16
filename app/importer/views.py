"""Administration → Import: upload a database, preview, then import.

The uploaded file is stored under ``DATA_DIR/imports`` with a random name
only between preview and confirmation and deleted afterwards.
"""

import os
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views import View
from inertia import render as inertia_render

from app.core.permissions import user_is_admin
from app.importer.elo_import import elo_accounts, import_elo
from app.importer.penalty_import import import_penalty
from app.importer.report import ImportAborted

SESSION_KEY = "importer_pending"
MAX_BYTES = 200 * 1024 * 1024


def _upload_dir() -> str:
    base = os.path.dirname(str(settings.DATABASES["default"]["NAME"]))
    path = os.path.join(base, "imports")
    os.makedirs(path, exist_ok=True)
    return path


def _drop(pending: dict | None) -> None:
    if pending and pending.get("path") and os.path.isfile(pending["path"]):
        os.remove(pending["path"])


class ImportView(LoginRequiredMixin, View):
    template_name = "importer/import.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not user_is_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        _drop(request.session.pop(SESSION_KEY, None))
        return self._render(request, {"nav_section": "admin"})

    def _render(self, request, context):
        """React page: upload form, preview (with account mapping) or result."""
        report = context.get("report")
        pending = context.get("pending")
        stage = "done" if context.get("done") else ("preview" if report else "upload")
        props = {
            "stage": stage,
            "report": (
                {
                    "kind": report.kind,
                    "ok": report.ok,
                    "counts": [{"label": str(k), "value": v} for k, v in report.counts.items()],
                    "checks": [
                        {"label": str(label), "ok": bool(ok), "detail": str(detail or "")}
                        for label, ok, detail in report.checks
                    ],
                    "warnings": [str(w) for w in report.warnings],
                    "matched": [
                        {"what": str(what), "source": str(a), "portal": str(b)}
                        for what, a, b in report.matched
                    ],
                }
                if report
                else None
            ),
            "pending": (
                {
                    "name": pending.get("name", ""),
                    "kind": pending.get("kind", ""),
                    "accounts": [
                        {"id": a["id"], "username": a["username"], "role": str(a.get("role", ""))}
                        for a in pending.get("accounts", [])
                    ],
                }
                if pending
                else None
            ),
            "portalUsers": [
                {"value": str(u.pk), "label": u.email} for u in context.get("portal_users", [])
            ],
        }
        return inertia_render(request, "Admin/Import", props=props, template_data=context)

    def post(self, request):
        action = request.POST.get("action")
        if action == "preview":
            return self._preview(request)
        if action == "run":
            return self._run(request)
        return redirect("importer:import")

    def _options(self, request, pending) -> dict:
        opts = {}
        if pending["kind"] == "elo":
            opts["replace"] = pending.get("replace", False)
            opts["email_domain"] = pending.get("email_domain") or "elo.invalid"
            opts["account_map"] = {
                acc["username"]: request.POST.get(f"map_{acc['id']}")
                for acc in pending.get("accounts", [])
                if request.POST.get(f"map_{acc['id']}")
            }
        return opts

    def _preview(self, request):
        upload = request.FILES.get("file")
        kind = request.POST.get("kind")
        if kind not in ("elo", "penalty") or upload is None:
            messages.error(request, _("Choose the kind of database and a file."))
            return redirect("importer:import")
        if upload.size > MAX_BYTES:
            messages.error(request, _("The file is too large."))
            return redirect("importer:import")
        _drop(request.session.pop(SESSION_KEY, None))
        path = os.path.join(_upload_dir(), f"{secrets.token_hex(12)}.sqlite3")
        with open(path, "wb") as fh:
            fh.writelines(upload.chunks())
        pending = {
            "kind": kind,
            "path": path,
            "name": upload.name,
            "replace": request.POST.get("replace") in ("on", "1", "true"),
            "email_domain": (request.POST.get("email_domain") or "").strip(),
        }
        try:
            if kind == "elo":
                pending["accounts"] = elo_accounts(path)
                report = import_elo(path, dry_run=True, **self._options(request, pending))
            else:
                report = import_penalty(path, dry_run=True)
        except ImportAborted as exc:
            _drop(pending)
            messages.error(request, str(exc))
            return redirect("importer:import")
        request.session[SESSION_KEY] = pending
        return self._render(
            request,
            {
                "pending": pending,
                "report": report,
                "portal_users": get_user_model().objects.order_by("email"),
                "nav_section": "admin",
            },
        )

    def _run(self, request):
        pending = request.session.get(SESSION_KEY)
        if not pending or not os.path.isfile(pending.get("path", "")):
            messages.error(request, _("The upload has expired. Please upload the file again."))
            return redirect("importer:import")
        try:
            if pending["kind"] == "elo":
                report = import_elo(
                    pending["path"], actor=request.user, **self._options(request, pending)
                )
            else:
                report = import_penalty(pending["path"], actor=request.user)
        except ImportAborted as exc:
            messages.error(request, str(exc))
            return redirect("importer:import")
        finally:
            _drop(request.session.pop(SESSION_KEY, None))
        messages.success(request, _("Import finished."))
        return self._render(request, {"report": report, "done": True, "nav_section": "admin"})
