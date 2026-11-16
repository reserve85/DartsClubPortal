"""Club logo (light + dark variant) shown in the app header.

Files live in ``MEDIA_ROOT/branding`` (data volume). Admins upload them under
Administration -> Club logo; the Elo import takes them over from an Elo
backup ZIP (``uploads/club_logo_*.png``).
"""

import io
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from inertia import render as inertia_render

from app.core.permissions import user_is_admin

KINDS = ("light", "dark")
MAX_BYTES = 5 * 1024 * 1024


def _dir() -> str:
    path = os.path.join(settings.MEDIA_ROOT, "branding")
    os.makedirs(path, exist_ok=True)
    return path


def _path(kind: str) -> str:
    return os.path.join(_dir(), f"logo-{kind}.png")


def logo_urls() -> dict:
    out = {}
    for kind in KINDS:
        path = _path(kind)
        out[kind] = (
            f"{reverse('club_logo', args=[kind])}?v={int(os.path.getmtime(path))}"
            if os.path.isfile(path)
            else ""
        )
    return out


def save_logo(kind: str, data: bytes) -> None:
    """Store a logo as PNG (max 512 px high, aspect ratio kept)."""
    from PIL import Image

    if kind not in KINDS:
        raise ValueError(kind)
    if len(data) > MAX_BYTES:
        raise ValueError(_("The picture is too large (max. 5 MB)."))
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise ValueError(_("This file is not a picture.")) from exc
    img = img.convert("RGBA")
    if img.height > 512:
        img = img.resize((round(img.width * 512 / img.height), 512), Image.LANCZOS)
    img.save(_path(kind), "PNG")


def remove_logo(kind: str) -> None:
    if kind in KINDS and os.path.isfile(_path(kind)):
        os.remove(_path(kind))


class LogoFileView(View):
    """Public (the login page shows the logo too)."""

    def get(self, request, kind):
        if kind not in KINDS or not os.path.isfile(_path(kind)):
            raise Http404
        with open(_path(kind), "rb") as fh:
            response = HttpResponse(fh.read(), content_type="image/png")
        response["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


class LogoAdminView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not user_is_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return inertia_render(request, "Admin/Branding", props={"logo": logo_urls()})

    def post(self, request):
        kind = request.POST.get("kind")
        if kind not in KINDS:
            raise PermissionDenied
        if request.POST.get("remove"):
            remove_logo(kind)
            messages.success(request, _("Logo removed."))
        elif request.FILES.get("logo"):
            try:
                save_logo(kind, request.FILES["logo"].read())
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, _("Logo saved."))
        return redirect("club_logo_admin")
