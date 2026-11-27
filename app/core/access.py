"""Per-user module access and the start page.

A module is usable for a user when it is enabled for the installation
(``MODULES``) AND the account may use it (``elo_access`` / ``penalty_access``).
Admins always have every enabled module. The check runs centrally in
:class:`ModuleAccessMiddleware`, so no view can forget it.
"""

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from app.core.modules import ELO, PENALTY, enabled_modules
from app.core.permissions import user_admin_scopes

# URL namespaces / names that belong to a module.
MODULE_NAMESPACES = {
    "dashboard": PENALTY,
    "teams": PENALTY,
    # "players" (members) belongs to both modules; the penalty profile page
    # checks the module itself (PlayerDetailView).
    "matchdays": PENALTY,
    "penalties": PENALTY,
    "elo": ELO,
}
PENALTY_URL_NAMES = frozenset(
    {
        "season_list",
        "season_create",
        "season_update",
        "season_delete",
        "season_set_default",
        "season_set",
    }
)
_FLAG = {ELO: "elo_access", PENALTY: "penalty_access"}


def has_module(user, module: str) -> bool:
    if module not in enabled_modules():
        return False
    if not user or not user.is_authenticated:
        return False
    scopes = user_admin_scopes(user)
    if "portal" in scopes or module in scopes:
        return True
    return bool(getattr(user, _FLAG[module], True))


def user_modules(user) -> dict[str, bool]:
    return {name: has_module(user, name) for name in (ELO, PENALTY)}


def module_of(resolver_match) -> str | None:
    if resolver_match is None:
        return None
    if resolver_match.url_name in PENALTY_URL_NAMES and not resolver_match.namespace:
        return PENALTY
    return MODULE_NAMESPACES.get((resolver_match.namespaces or [""])[0])


class ModuleAccessMiddleware:
    """403 for pages of a module the signed-in user may not use."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return
        module = module_of(getattr(request, "resolver_match", None))
        if module is not None and not has_module(user, module):
            raise PermissionDenied
        return


START_URLS = {
    ELO: "elo:ranking",
    PENALTY: "dashboard:financial_overview",
}


def start_url(user) -> str:
    """URL of the user's start page (user choice -> club default -> first module)."""
    mods = user_modules(user)
    choice = getattr(user, "start_page", "auto") or "auto"
    if choice == "auto":
        # A person (linked player) starts on "My overview"; other accounts
        # (e.g. the club account) on the club's default.
        if getattr(user, "player_link_id", None):
            choice = "overview"
        else:
            choice = getattr(settings, "DEFAULT_START_PAGE", ELO)
    if choice == "overview" and any(mods.values()):
        return reverse("overview")
    if choice in START_URLS and mods.get(choice):
        return reverse(START_URLS[choice])
    for name in (ELO, PENALTY):
        if mods.get(name):
            return reverse(START_URLS[name])
    return reverse("overview")
