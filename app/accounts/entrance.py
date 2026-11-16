"""The entrance pages (login, sign-up, password reset, e-mail confirmation ...)
as the React page ``Auth/Entrance``.

django-allauth renders its pages as TemplateResponses (``account/login.html``
...). Instead of overriding every allauth view, this middleware swaps such a
response for the Inertia page and hands it the form (as field list) plus the
few facts the page needs. allauth keeps doing all the work: validation, rate
limits, redirects, e-mails.
"""

from django.conf import settings
from django.urls import reverse
from inertia import render as inertia_render

from app.core.inertia_utils import form_errors, form_schema

# allauth template -> page kind
KINDS = {
    "account/login.html": "login",
    "account/signup.html": "signup",
    "account/password_reset.html": "password_reset",
    "account/password_reset_done.html": "password_reset_done",
    "account/password_reset_from_key.html": "password_reset_key",
    "account/password_reset_from_key_done.html": "password_reset_key_done",
    "account/email_confirm.html": "email_confirm",
    "account/verification_sent.html": "verification_sent",
    "account/logout.html": "logout",
    "account/password_change.html": "password_change",
    "account/account_inactive.html": "inactive",
}


def entrance_response(request, kind: str, context: dict | None = None, **extra):
    """Render ``Auth/Entrance`` for ``kind`` (also used by the invite and QR pages)."""
    context = context or {}
    form = context.get("form")
    honeypot = getattr(settings, "ACCOUNT_SIGNUP_FORM_HONEYPOT_FIELD", None)
    props = {
        "kind": kind,
        "fields": form_schema(form, exclude=(honeypot,)) if form is not None else [],
        "errors": form_errors(form) if form is not None and form.is_bound else {},
        "action": request.get_full_path(),
        **extra,
    }
    confirmation = context.get("confirmation")
    if kind == "email_confirm":
        props["confirmation"] = (
            {
                "email": confirmation.email_address.email,
                "canConfirm": bool(context.get("can_confirm", True)),
                "action": reverse("account_confirm_email", args=[confirmation.key]),
            }
            if confirmation
            else None
        )
    if kind == "password_reset_key":
        props["tokenFail"] = bool(context.get("token_fail"))
    data = {k: v for k, v in context.items() if k not in ("view",)}
    return inertia_render(request, "Auth/Entrance", props=props, template_data=data)


class InertiaEntranceMiddleware:
    """Swap allauth's template responses for the React entrance page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_template_response(self, request, response):
        names = response.template_name
        if isinstance(names, str):
            names = [names]
        kind = next((KINDS[n] for n in (names or []) if n in KINDS), None)
        if kind is None:
            return response
        page = entrance_response(request, kind, dict(response.context_data or {}))
        page.status_code = response.status_code
        # Django renders template responses after this hook: the Inertia
        # response is already final, so "rendering" returns it unchanged.
        page.render = lambda: page
        return page
