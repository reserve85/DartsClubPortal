"""QR-code login for shared club accounts (e.g. the tablet at the board).

New QR codes point to ``/accounts/qr/#t=<token>``. The token sits in the URL
*fragment*, which browsers never send to a server, so it never shows up in
access logs or proxies; the page posts it here. A token is bound to the
account's current password: changing the password invalidates every printed
code. Admin accounts can never log in by QR code.

Old printed codes of the Elo system keep working after the import:

- ``/ui/qr-login#t=<jwt>``: the old signed token (needs ``ELO_LEGACY_JWT_SECRET``),
- ``/auth/auto-login?u=<name>&p=<password>``: the oldest codes with the
  password in the URL (switch off with ``ELO_LEGACY_QR_LOGIN=false`` once
  every old code has been replaced).
"""

import base64
import hashlib
import hmac
import io
import json
import logging

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.crypto import salted_hmac
from django.utils.translation import gettext as _
from django.views import View

from app.core.models import AuditAction
from app.core.permissions import user_is_admin
from app.core.services import log_action

logger = logging.getLogger("app.accounts")
SALT = "app.accounts.qr-login"
BACKEND = "django.contrib.auth.backends.ModelBackend"


def _fingerprint(user) -> str:
    return salted_hmac(SALT, user.password or "").hexdigest()[:24]


def make_token(user) -> str:
    return signing.dumps({"u": user.pk, "f": _fingerprint(user)}, salt=SALT, compress=True)


def qr_allowed(user) -> bool:
    return bool(
        user is not None
        and user.is_active
        and getattr(user, "is_approved", True)
        and not user_is_admin(user)
        and user.has_usable_password()
    )


def user_for_token(token: str):
    try:
        data = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None
    user = get_user_model().objects.filter(pk=data.get("u")).first()
    if user is None or not hmac.compare_digest(str(data.get("f", "")), _fingerprint(user)):
        return None
    return user if qr_allowed(user) else None


# ------------------------------------------------------------- legacy (Elo)
def _b64url(raw: str) -> bytes:
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def _legacy_jwt_payload(token: str) -> dict | None:
    """Verify an HS256 JWT of the old Elo system (no third-party library)."""
    secret = getattr(settings, "ELO_LEGACY_JWT_SECRET", "")
    if not secret:
        return None
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        header = json.loads(_b64url(header_b64))
        if header.get("alg") != "HS256":
            return None
        expected = hmac.new(
            secret.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64url(sig_b64)):
            return None
        payload = json.loads(_b64url(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    return payload if payload.get("purpose") == "qr" else None


def legacy_user_for_jwt(token: str):
    payload = _legacy_jwt_payload(token)
    if payload is None:
        return None
    try:
        elo_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
    user = get_user_model().objects.filter(legacy_elo_id=elo_id).first()
    if user is None or not qr_allowed(user):
        return None
    # The old token is bound to the old password hash: still valid only while
    # the imported hash is unchanged ("argon2" + the Elo hash).
    if not (user.password or "").startswith("argon2$"):
        return None
    old_hash = user.password[len("argon2") :]
    secret = settings.ELO_LEGACY_JWT_SECRET
    fingerprint = hmac.new(secret.encode(), old_hash.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(str(payload.get("pwv", "")), fingerprint):
        return None
    return user


def _finish_login(request, user, source: str):
    login(request, user, backend=BACKEND)
    log_action(AuditAction.LOGIN, user=user, target=user, metadata={"source": source})
    from app.core.access import start_url

    return start_url(user)


class QrLoginView(View):
    """GET: page that reads the fragment token; POST: log in with it."""

    legacy = False

    def get(self, request):
        from app.accounts.entrance import entrance_response

        return entrance_response(
            request,
            "qr_login",
            {"legacy": self.legacy},
            qr={"postUrl": reverse("accounts:qr_login"), "legacy": bool(self.legacy)},
        )

    def post(self, request):
        token = (request.POST.get("token") or "").strip()
        legacy = request.POST.get("legacy") == "1"
        user = legacy_user_for_jwt(token) if legacy else user_for_token(token)
        if user is None:
            logger.info("QR login refused (legacy=%s).", legacy)
            return JsonResponse(
                {"detail": _("This QR code is no longer valid. Please log in manually.")},
                status=401,
            )
        return JsonResponse(
            {"redirect": _finish_login(request, user, "qr_legacy" if legacy else "qr")}
        )


class LegacyAutoLoginView(View):
    """Oldest Elo QR codes: /auth/auto-login?u=<login name>&p=<password>."""

    def get(self, request):
        if not getattr(settings, "ELO_LEGACY_QR_LOGIN", True):
            return redirect("account_login")
        name, password = request.GET.get("u", ""), request.GET.get("p", "")
        user = get_user_model().objects.filter(legacy_username=name).first() if name else None
        if user is None or not qr_allowed(user) or not user.check_password(password):
            logger.info("Legacy auto-login refused for '%s'.", name[:40])
            return redirect("account_login")
        return redirect(_finish_login(request, user, "qr_password_legacy"))


class UserQrCodeView(LoginRequiredMixin, View):
    """Admin: printable QR code that logs a shared account in."""

    def get(self, request, pk):
        if not user_is_admin(request.user):
            raise PermissionDenied
        target = get_object_or_404(get_user_model(), pk=pk)
        ctx = {"target": target, "allowed": qr_allowed(target)}
        if ctx["allowed"]:
            url = (
                request.build_absolute_uri(reverse("accounts:qr_login"))
                + "#t="
                + make_token(target)
            )
            if getattr(settings, "PUBLIC_SITE_URL", ""):
                url = (
                    settings.PUBLIC_SITE_URL
                    + reverse("accounts:qr_login")
                    + "#t="
                    + make_token(target)
                )
            ctx["png"] = _qr_png_data_uri(url)
            ctx["url"] = url
        from inertia import render as inertia_render

        props = {
            "target": {"email": target.email, "name": target.full_name},
            "allowed": ctx["allowed"],
            "png": ctx.get("png", ""),
            "backUrl": reverse("accounts:user_list"),
        }
        return inertia_render(request, "Admin/UserQr", props=props, template_data=ctx)


def _qr_png_data_uri(url: str) -> str:
    import qrcode

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
