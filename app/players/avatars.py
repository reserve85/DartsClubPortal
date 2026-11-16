"""Player avatars: upload (square 256 px), serve, and the name -> picture map.

Pictures live in ``MEDIA_ROOT/avatars`` (next to the SQLite file, i.e. on the
data volume). Every round ``.ui-avatar`` in the app shows the picture through
``club-ui.js`` and the ``avatar-map`` JSON that ``base.html`` embeds.
"""

import io
import os
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views import View

from app.core.permissions import user_is_elo_admin, user_is_penalty_admin
from app.players.models import Player

SIZE = 256
MAX_UPLOAD = 8 * 1024 * 1024


def avatar_dir() -> str:
    path = os.path.join(settings.MEDIA_ROOT, "avatars")
    os.makedirs(path, exist_ok=True)
    return path


def avatar_url(player) -> str:
    if not player.avatar:
        return ""
    return reverse("player_avatar", args=[player.avatar])


def avatar_map() -> dict[str, str]:
    return {
        p.name: reverse("player_avatar", args=[p.avatar])
        for p in Player.objects.exclude(avatar="").only("name", "avatar")
    }


def save_avatar(player, upload) -> None:
    from PIL import Image, ImageOps

    if upload.size > MAX_UPLOAD:
        raise ValueError(_("The picture is too large (max. 8 MB)."))
    try:
        img = Image.open(upload)
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as exc:
        raise ValueError(_("This file is not a picture.")) from exc
    img = ImageOps.fit(img, (SIZE, SIZE), Image.LANCZOS)
    name = f"{player.pk}-{secrets.token_hex(6)}.jpg"
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=86)
    with open(os.path.join(avatar_dir(), name), "wb") as fh:
        fh.write(buf.getvalue())
    remove_avatar(player, save=False)
    player.avatar = name
    player.save(update_fields=["avatar"])


def remove_avatar(player, save=True) -> None:
    if player.avatar:
        old = os.path.join(avatar_dir(), os.path.basename(player.avatar))
        if os.path.isfile(old):
            os.remove(old)
        player.avatar = ""
        if save:
            player.save(update_fields=["avatar"])


class AvatarFileView(LoginRequiredMixin, View):
    def get(self, request, name):
        path = os.path.join(avatar_dir(), os.path.basename(name))
        if not os.path.isfile(path):
            raise Http404
        with open(path, "rb") as fh:  # ~20 KB: read at once, no open handle
            response = HttpResponse(fh.read(), content_type="image/jpeg")
        response["Cache-Control"] = "private, max-age=31536000, immutable"
        return response


class AvatarUploadView(LoginRequiredMixin, View):
    """POST: upload or remove ("remove=1") the picture of a player.

    Members change their own linked player, admins any player (``player``).
    """

    def post(self, request):
        pid = request.POST.get("player")
        if pid and pid.isdigit() and int(pid) != getattr(request.user, "player_link_id", None):
            if not (user_is_elo_admin(request.user) or user_is_penalty_admin(request.user)):
                raise PermissionDenied
            player = get_object_or_404(Player, pk=int(pid))
        else:
            player = request.user.player_link
            if player is None:
                raise PermissionDenied
        if request.POST.get("remove"):
            remove_avatar(player)
            messages.success(request, _("Picture removed."))
        elif request.FILES.get("avatar"):
            try:
                save_avatar(player, request.FILES["avatar"])
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, _("Picture saved."))
        nxt = request.POST.get("next") or reverse("accounts:settings")
        if not url_has_allowed_host_and_scheme(nxt, {request.get_host()}):
            nxt = reverse("accounts:settings")
        return redirect(nxt)


def avatars_for(player_ids) -> dict[int, str]:
    """{player_id: picture URL} for the given players (only those with a picture)."""
    rows = (
        Player.objects.filter(pk__in=list(player_ids))
        .exclude(avatar="")
        .values_list("pk", "avatar")
    )
    return {pk: reverse("player_avatar", args=[name]) for pk, name in rows}
