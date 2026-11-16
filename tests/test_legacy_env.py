"""Environment of the old EloRankingSystem container keeps working."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _settings(env: dict) -> dict:
    code = (
        "import json, django; from django.conf import settings as s;"
        "print(json.dumps({'k': s.ELO['K_FACTOR'], 'best': s.ELO['BEST_OF_LEGS'],"
        "'url': s.PUBLIC_SITE_URL, 'name': s.SITE_NAME, 'tz': s.TIME_ZONE,"
        "'jwt': s.ELO_LEGACY_JWT_SECRET, 'qr': s.ELO_LEGACY_QR_LOGIN}))"
    )
    clean = {k: v for k, v in os.environ.items() if k not in env and not k.startswith("ELO_")}
    out = subprocess.run(
        [sys.executable, "-c", code],
        env={**clean, **env, "DJANGO_SETTINGS_MODULE": "config.settings"},
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_old_elo_names_are_used():
    got = _settings(
        {
            "K_FACTOR": "40",
            "BEST_OF_LEGS": "7",
            "APP_BASE_URL": "https://darts.example.com/",
            "CLUB_NAME": "Example Darts",
            "TIMEZONE": "Europe/Vienna",
            "JWT_SECRET": "old-secret",
            "LEGACY_QR_LOGIN_ENABLED": "false",
        }
    )
    assert got == {
        "k": 40,
        "best": 7,
        "url": "https://darts.example.com",
        "name": "Example Darts",
        "tz": "Europe/Vienna",
        "jwt": "old-secret",
        "qr": False,
    }


def test_portal_name_wins_over_the_old_one():
    got = _settings({"K_FACTOR": "40", "ELO_K_FACTOR": "24"})
    assert got["k"] == 24
