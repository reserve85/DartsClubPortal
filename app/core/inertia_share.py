"""Props every Inertia page receives (user, rights, menu, translations).

The menu is built HERE from the same permission helpers the views use, so
the frontend never decides on its own what an account may see.
"""

from functools import lru_cache

from django.conf import settings
from django.urls import NoReverseMatch, reverse
from django.utils import translation
from django.utils.translation import gettext as _
from inertia import share

from app.core.access import has_module
from app.core.branding import logo_urls
from app.core.frontend_i18n import MSGIDS
from app.core.modules import ELO, PENALTY, enabled_modules
from app.core.permissions import (
    user_admin_scopes,
    user_is_admin,
    user_is_captain,
    user_is_portal_admin,
)


def _build_info() -> dict:
    """Version line of the footer (APP_VERSION / GIT_COMMIT / BUILD_DATE)."""
    from app.core.version import get_version_info

    info = get_version_info(getattr(settings, "TIME_ZONE", "UTC"))
    return {
        "version": info["version"],
        "commit": info["git_commit"],
        "date": info["build_date"],
        "github": info["github_url"],
        "release": info["release_url"],
    }


def _url(name, *args):
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return None


def _item(label, name, icon, *args, **extra):
    url = _url(name, *args)
    return {"label": label, "href": url, "icon": icon, **extra} if url else None


def navigation(user) -> list[dict]:
    """Menu groups for this account: Elo · Penalty · Captain · Administration."""
    groups = []
    scopes = user_admin_scopes(user)
    is_admin = "penalty" in scopes  # team management of every team
    if has_module(user, ELO):
        items = [
            _item(_("Ranking"), "elo:ranking", "trophy"),
            _item(_("Enter match"), "elo:match_create", "plus"),
            _item(_("Matches"), "elo:match_list", "list"),
            _item(_("Head-to-head"), "elo:h2h", "swords"),
            _item(_("All-time Elo"), "elo:all_time", "crown"),
        ]
        groups.append(
            {"key": "elo", "label": "Elo", "icon": "target", "items": [i for i in items if i]}
        )
    if has_module(user, PENALTY):
        items = [_item(_("Financial overview"), "dashboard:financial_overview", "coins")]
        groups.append(
            {"key": "penalty", "label": "Penalty", "icon": "cash", "items": [i for i in items if i]}
        )
    if has_module(user, PENALTY) and (is_admin or user_is_captain(user)):
        team = getattr(user, "team", None)
        items = [
            _item(_("Matchdays"), "matchdays:matchday_list", "calendar"),
            _item(_("Teams & Players"), "teams:team_list", "users"),
            _item(_("Penalty catalog"), "penalties:catalog_list", "book"),
            _item(_("Cash box"), "teams:cashier_list", "wallet"),
        ]
        label = _("Captain") if not is_admin else _("Team management")
        groups.append(
            {
                "key": "captain",
                "label": label,
                "hint": team.name if team is not None and not is_admin else "",
                "icon": "flag",
                "items": [i for i in items if i],
            }
        )
    if scopes:
        portal = "portal" in scopes
        items = [
            # Every person (teams, Elo, account) - for every admin area.
            _item(_("Members"), "players:player_list", "users-group"),
            _item(_("Users"), "accounts:user_list", "user-cog") if portal else None,
            _item(_("Elo administration"), "elo:manage", "adjustments")
            if "elo" in scopes and has_module(user, ELO)
            else None,
            _item(_("Seasons"), "season_list", "calendar-cog")
            if "penalty" in scopes and PENALTY in enabled_modules()
            else None,
            _item(_("Import"), "importer:import", "upload") if portal else None,
            _item(_("Club logo"), "club_logo_admin", "photo") if portal else None,
            _item(_("Audit"), "audit_list", "history") if portal else None,
        ]
        groups.append(
            {
                "key": "admin",
                "label": _("Administration"),
                "icon": "shield",
                "items": [i for i in items if i],
            }
        )
    return groups


@lru_cache(maxsize=8)
def _catalog(language: str) -> dict:
    with translation.override(language):
        return {m: str(_(m)) for m in MSGIDS}


def user_payload(user) -> dict | None:
    if not user.is_authenticated:
        return None
    from app.players.avatars import avatar_url

    player = getattr(user, "player_link", None)
    team = getattr(user, "team", None)
    return {
        "id": user.pk,
        "email": user.email,
        "name": (player.name if player else "") or user.full_name or user.email,
        "avatar": avatar_url(player) if player else "",
        "playerId": player.pk if player else None,
        "role": user.role,
        "isAdmin": user_is_admin(user),
        "adminScopes": sorted(user_admin_scopes(user)),
        "isCaptain": user_is_captain(user),
        "captainOf": {"id": team.pk, "name": team.name} if team is not None else None,
        "modules": {ELO: has_module(user, ELO), PENALTY: has_module(user, PENALTY)},
        "theme": getattr(user, "preferred_theme", "auto") or "auto",
    }


def _flash_messages(request) -> list[dict]:
    """Consume the pending Django messages for the toasts of the React shell."""
    from django.contrib.messages import get_messages

    return [
        {"message": str(m.message), "level": m.level_tag, "tags": m.tags}
        for m in get_messages(request)
    ]


class InertiaShareMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        language = translation.get_language() or settings.LANGUAGE_CODE
        share(
            request,
            site=lambda: {
                "name": settings.SITE_NAME,
                "language": language,
                "logo": logo_urls(),
                "build": _build_info(),
            },
            auth=lambda: {"user": user_payload(user)},
            # Django messages (success / error after a save) -> toasts.
            flash=lambda: {"messages": _flash_messages(request)},
            nav=lambda: navigation(user) if user.is_authenticated else [],
            i18n=lambda: _catalog(language),
            urls=lambda: {
                "home": reverse("home"),
                "overview": _url("overview"),
                "settings": _url("accounts:settings"),
                "logout": _url("account_logout"),
                "notifications": _url("notifications:unread"),
                "imprint": _url("imprint"),
                "privacy": _url("privacy"),
                "rights": _url("rights"),
                # Signed-in users switch the language on the settings page only.
                "setLanguage": None if user.is_authenticated else _url("set_language"),
            },
            counts=lambda: _counts(user),
        )
        return self.get_response(request)


def _counts(user) -> dict:
    if not user.is_authenticated:
        return {}
    from app.notifications.inapp import unread_count

    out = {"notifications": unread_count(user)}
    if user_is_portal_admin(user):
        from django.contrib.auth import get_user_model

        out["approvals"] = get_user_model().objects.filter(approval_status="pending").count()
    return out


class InertiaFallbackMiddleware:
    """An Inertia visit that lands on a classic (non-Inertia) page becomes a
    full page load (409 + X-Inertia-Location) instead of an error popup.

    Keeps every link working while pages move to React one by one, and makes
    allauth pages (login, logout, password reset) reachable from the app.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.headers.get("X-Inertia")
            and not response.has_header("X-Inertia")
            and response.status_code == 200
            and "text/html" in response.get("Content-Type", "")
        ):
            from django.http import HttpResponse

            fallback = HttpResponse(status=409)
            fallback["X-Inertia-Location"] = request.build_absolute_uri()
            return fallback
        return response
