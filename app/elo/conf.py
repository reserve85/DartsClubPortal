"""Elo knobs (environment driven, see ``config/settings.py`` -> ``ELO``).

Read through these helpers so tests can override ``settings.ELO`` per test.
"""

from django.conf import settings

DEFAULTS = {
    "DEFAULT_ELO": 1200,
    "K_FACTOR": 32,
    "INACTIVITY_MONTHS": 3,
    "HIGH_FINISH_MIN": 100,
    "HIGH_FINISH_MAX": 170,
    "LOW_DARTS_MIN": 9,
    "LOW_DARTS_MAX": 21,
    "BEST_OF_LEGS": 5,
}


def elo_setting(key: str) -> int:
    return int(getattr(settings, "ELO", {}).get(key, DEFAULTS[key]))
