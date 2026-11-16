"""Theme tests — endpoint persistence + server-rendered data attributes (dark mode)."""

import pytest
from django.test import Client
from django.urls import reverse

from app.core.choices import THEME_COOKIE_NAME
from tests.conftest import inertia_props

pytestmark = pytest.mark.django_db


def test_theme_endpoint_updates_preference(admin_client, admin_user):
    response = admin_client.post(reverse("accounts:settings_theme"), {"theme": "dark"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "theme": "dark"}
    admin_user.refresh_from_db()
    assert admin_user.preferred_theme == "dark"


def test_theme_endpoint_accepts_all_choices(admin_client, admin_user):
    for value in ("auto", "light", "dark"):
        response = admin_client.post(reverse("accounts:settings_theme"), {"theme": value})
        assert response.status_code == 200
        admin_user.refresh_from_db()
        assert admin_user.preferred_theme == value


def test_theme_endpoint_rejects_invalid(admin_client, admin_user):
    response = admin_client.post(reverse("accounts:settings_theme"), {"theme": "neon"})
    assert response.status_code == 400
    assert response.json()["ok"] is False
    admin_user.refresh_from_db()
    assert admin_user.preferred_theme != "neon"


def test_theme_endpoint_requires_login(db):
    response = Client().post(reverse("accounts:settings_theme"), {"theme": "dark"})
    assert response.status_code == 302
    assert "login" in response.url


def test_theme_endpoint_get_not_allowed(admin_client):
    assert admin_client.get(reverse("accounts:settings_theme")).status_code == 405


def test_theme_switcher_buttons_rendered_for_anonymous(db):
    """Anonymous visitors (login, signup) get the switcher: auto / light / dark."""
    from pathlib import Path

    from django.conf import settings

    props = inertia_props(Client().get(reverse("account_login")))
    assert props["auth"]["user"] is None
    page = Path(settings.BASE_DIR, "frontend/src/pages/Auth/Entrance.tsx").read_text("utf-8")
    assert all(f'value: "{v}"' in page for v in ("auto", "light", "dark"))
    assert "dpm_theme=" in page  # the choice survives page changes (cookie)


def test_switchers_hidden_for_authenticated_users(admin_client):
    """Signed-in users have NO language/theme switcher in the navbar.

    Both preferences live on the Settings page only.
    """
    html = admin_client.get(reverse("dashboard:index")).content.decode()
    assert "data-theme-choice-btn" not in html
    assert reverse("set_language") not in html


def test_anonymous_has_no_theme_url(db):
    response = Client().get(reverse("account_login"))
    assert inertia_props(response)["auth"]["user"] is None  # no account to save into
    assert 'var pref = "auto"' in response.content.decode()  # default before first paint


def test_language_switcher_renders_on_login_page(db):
    props = inertia_props(Client().get(reverse("account_login")))
    assert props["urls"]["setLanguage"] == reverse("set_language")
    assert props["site"]["language"] in ("de", "en")


# ---------------------------------------------------------------------------
# Flash-free rendering (dark mode must be dark from the first painted frame)
# ---------------------------------------------------------------------------


def test_head_resolves_theme_before_stylesheet(db):
    """The choice must be resolved inline in <head>, before the stylesheet.

    Bootstrap only knows ``light``/``dark``, so a server-rendered ``auto``
    would paint the LIGHT theme first and flash bright on every page change
    until theme.js (end of <body>) runs.
    """
    html = Client().get(reverse("account_login")).content.decode()
    head = html.split("</head>")[0]
    # Earliest bytes carry the dark-canvas hint, the inline resolver sets the
    # colour scheme + canvas before the app bundle loads.
    assert head.index('name="color-scheme"') < head.index("<script")
    resolver = 'setAttribute("data-mantine-color-scheme"'
    assert resolver in head
    assert head.index(resolver) < head.index('type="module"')
    assert "root.style.backgroundColor" in head


def test_anonymous_theme_cookie_is_rendered(db):
    """The dpm_theme cookie keeps an anonymous toggle across page changes."""
    client = Client()
    client.cookies[THEME_COOKIE_NAME] = "dark"
    html = client.get(reverse("account_login")).content.decode()
    assert 'var pref = "dark"' in html


def test_invalid_theme_cookie_falls_back_to_auto(db):
    client = Client()
    client.cookies[THEME_COOKIE_NAME] = "neon"
    html = client.get(reverse("account_login")).content.decode()
    assert 'var pref = "auto"' in html and "neon" not in html
