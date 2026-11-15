"""Club portal: module switch (MODULES) and configurable site name."""

import importlib

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.urls import clear_url_caches, reverse

from app.core.modules import parse_modules


def _reload_urls():
    import config.urls

    clear_url_caches()
    importlib.reload(config.urls)
    clear_url_caches()


@pytest.fixture
def modules(settings):
    """Switch MODULES for one test; the URL configuration is rebuilt for it."""

    def apply(value):
        settings.MODULES = value
        _reload_urls()

    yield apply
    settings.MODULES = ["strafen"]
    _reload_urls()


class TestParseModules:
    def test_comma_separated_and_case_insensitive(self):
        assert parse_modules(" Strafen , ") == frozenset({"strafen"})
        assert parse_modules([]) == frozenset()

    def test_unknown_module_is_a_configuration_error(self):
        with pytest.raises(ImproperlyConfigured, match="unknown"):
            parse_modules("strafen,kegeln")

    def test_module_not_in_this_version_yet(self):
        with pytest.raises(ImproperlyConfigured, match="not part of this version"):
            parse_modules("elo")


class TestPenaltyModuleOn:
    def test_start_page_is_the_financial_overview_as_before(self, admin_client):
        assert reverse("home") == "/"
        resp = admin_client.get("/")
        assert resp.status_code == 200
        assert resp.resolver_match.namespace == "dashboard"

    def test_penalty_menu_is_shown(self, admin_client):
        html = admin_client.get("/").content.decode()
        assert reverse("matchdays:matchday_list") in html


class TestPenaltyModuleOff:
    def test_penalty_pages_disappear(self, admin_client, modules):
        modules([])
        assert admin_client.get("/matchdays/").status_code == 404
        assert admin_client.get("/teams/").status_code == 404
        assert admin_client.get("/seasons/").status_code == 404

    def test_home_explains_that_no_module_is_on(self, admin_client, modules):
        modules([])
        resp = admin_client.get("/")
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "MODULES" in html
        assert "/matchdays/" not in html

    def test_base_functions_stay(self, admin_client, modules):
        modules([])
        assert admin_client.get(reverse("accounts:settings")).status_code == 200
        assert admin_client.get(reverse("audit_list")).status_code == 200
        assert admin_client.get(reverse("accounts:user_list")).status_code == 200

    def test_login_lands_on_the_portal_home(self, client, admin_user, modules):
        modules([])
        resp = client.post(reverse("account_login"), {"login": admin_user.email, "password": "pw"})
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/"


class TestSiteName:
    def test_site_name_is_configurable(self, client, db):
        with override_settings(SITE_NAME="SV Musterstadt Darts"):
            html = client.get(reverse("account_login")).content.decode()
        assert "SV Musterstadt Darts" in html
        assert "Darts Penalty Manager" not in html
