"""One-click unsubscribe links for every e-mail a user may switch off.

The link carries a signed token (user + mail kind); no login is needed.
GET shows a confirmation page, POST switches the preference off (mail
clients that prefetch links never unsubscribe anyone by accident).
"""

from django.contrib.auth import get_user_model
from django.core import signing
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from app.core.choices import PenaltyNotifyChoice

SALT = "app.notifications.unsubscribe"

# kind -> (label, field, value that means "off")
KINDS = {
    "penalty": (_("New penalties"), "penalty_notify_mode", PenaltyNotifyChoice.OFF),
    "repayment": (_("Payment confirmations"), "repayment_notify", False),
    "news": (_("Club news / round mails"), "club_news_optin", False),
    "elo_match": (_("Elo match results"), "elo_match_notify", False),
    "elo_monthly": (_("Monthly Elo summary"), "elo_monthly_summary", False),
}


def make_token(user, kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(kind)
    return signing.dumps({"u": user.pk, "k": kind}, salt=SALT, compress=True)


def read_token(token: str):
    """(user, kind) for a valid token, else (None, None)."""
    try:
        data = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None, None
    kind = data.get("k")
    if kind not in KINDS:
        return None, None
    user = get_user_model().objects.filter(pk=data.get("u")).first()
    return (user, kind) if user is not None else (None, None)


def unsubscribe(user, kind: str) -> None:
    _label, field, off = KINDS[kind]
    setattr(user, field, off)
    user.save(update_fields=[field])


def unsubscribe_path(user, kind: str) -> str:
    return reverse("notifications_manage:unsubscribe", args=[make_token(user, kind)])


def mail_context(user, kind: str) -> dict:
    """Context for e-mail templates: unsubscribe + settings links (absolute)."""
    from app.notifications.services import absolute_url

    return {
        "unsubscribe_url": absolute_url(unsubscribe_path(user, kind)),
        "unsubscribe_label": KINDS[kind][0],
        "settings_url": absolute_url(reverse("accounts:settings")),
    }
