"""Feature modules of the club portal and their on/off switch.

``MODULES`` (environment) lists the enabled modules, comma separated:

    MODULES=penalty        penalties only (default - behaves like DartsPenaltySystem)
    MODULES=elo            Elo ranking only
    MODULES=elo,penalty    both

A disabled module is invisible: no URLs, no menu entries, no tiles. Its apps
stay installed, so its tables and data survive and come back when it is
switched on again. The base (accounts, players, settings, audit) is always on.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

PENALTY = "penalty"
ELO = "elo"

# Known modules -> human label (shown in menus / overview tiles).
KNOWN_MODULES: dict[str, str] = {
    PENALTY: _("Penalties"),
    ELO: _("Elo ranking"),
}
# Modules whose code is part of this build. "elo" is added by the Elo port.
AVAILABLE_MODULES: frozenset[str] = frozenset({PENALTY})


def parse_modules(raw) -> frozenset[str]:
    """Validate the MODULES setting (list or comma separated string)."""
    if isinstance(raw, str):
        items = [x.strip().lower() for x in raw.split(",")]
    else:
        items = [str(x).strip().lower() for x in raw or []]
    items = [x for x in items if x]
    unknown = sorted(set(items) - set(KNOWN_MODULES))
    if unknown:
        raise ImproperlyConfigured(
            f"MODULES contains unknown module(s): {', '.join(unknown)}. "
            f"Known: {', '.join(sorted(KNOWN_MODULES))}."
        )
    missing = sorted(set(items) - AVAILABLE_MODULES)
    if missing:
        raise ImproperlyConfigured(
            f"MODULES enables {', '.join(missing)}, which is not part of this version yet."
        )
    return frozenset(items)


def enabled_modules() -> frozenset[str]:
    return parse_modules(getattr(settings, "MODULES", [PENALTY]))


def is_enabled(name: str) -> bool:
    return name in enabled_modules()
