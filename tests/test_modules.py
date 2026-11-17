"""Club portal: module switch (MODULES), per-user module access, start page."""

import importlib

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.urls import clear_url_caches, reverse

from app.core.modules import parse_modules
from tests.conftest import inertia_props


def _reload_urls():
    import config.urls

    clear_url_caches()
    importlib.reload(config.urls)
    clear_url_caches()


@pytest.fixture
def modules(settings):
    """Switch MODULES for one test; the URL configuration is rebuilt for it."""
    original = list(settings.MODULES)

    def apply(value):
        settings.MODULES = value
        _reload_urls()

    yield apply
    settings.MODULES = original
    _reload_urls()


class TestParseModules:
    def test_comma_separated_and_case_insensitive(self):
        assert parse_modules(" Penalty , ") == frozenset({"penalty"})
        assert parse_modules([]) == frozenset()

    def test_unknown_module_is_a_configuration_error(self):
        with pytest.raises(ImproperlyConfigured, match="unknown"):
            parse_modules("penalty,bowling")

    def test_both_modules_are_available(self):
        assert parse_modules("elo,penalty") == frozenset({"elo", "penalty"})
        assert parse_modules("elo") == frozenset({"elo"})


class TestStartPage:
    def test_default_start_page_is_the_elo_ranking(self, admin_client):
        assert reverse("home") == "/"
        resp = admin_client.get("/")
        assert resp.status_code == 302
        assert resp.headers["Location"] == reverse("elo:ranking")

    def test_user_choice_wins(self, admin_client, admin_user):
        admin_user.start_page = "penalty"
        admin_user.save()
        assert admin_client.get("/").headers["Location"] == reverse("dashboard:financial_overview")
        admin_user.start_page = "overview"
        admin_user.save()
        assert admin_client.get("/").headers["Location"] == reverse("overview")
        assert admin_client.get(reverse("overview")).status_code == 200

    def test_club_default_is_configurable(self, admin_client, settings):
        settings.DEFAULT_START_PAGE = "penalty"
        assert admin_client.get("/").headers["Location"] == reverse("dashboard:financial_overview")

    def test_menu_shows_both_modules(self, admin_client):
        html = admin_client.get(reverse("elo:ranking")).content.decode()
        assert reverse("matchdays:matchday_list") in html
        assert reverse("elo:match_create") in html
        assert reverse("overview") in html


class TestModuleAccess:
    def test_elo_only_account(self, player_client, player_user):
        player_user.penalty_access = False
        player_user.save()
        assert player_client.get("/").headers["Location"] == reverse("elo:ranking")
        assert player_client.get(reverse("elo:ranking")).status_code == 200
        assert player_client.get(reverse("dashboard:financial_overview")).status_code == 403
        nav = inertia_props(player_client.get(reverse("elo:ranking")))["nav"]
        hrefs = [i["href"] for g in nav for i in g["items"]]
        assert reverse("dashboard:financial_overview") not in hrefs
        fields = inertia_props(player_client.get(reverse("accounts:settings")))["fields"]
        assert "penalty_notify_mode" not in fields
        assert "elo_match_notify" in fields

    def test_penalty_only_account(self, player_client, player_user):
        player_user.elo_access = False
        player_user.save()
        assert player_client.get(reverse("elo:ranking")).status_code == 403
        assert player_client.get("/").headers["Location"] == reverse("dashboard:financial_overview")

    def test_admin_always_has_both(self, admin_client, admin_user):
        admin_user.elo_access = admin_user.penalty_access = False
        admin_user.save()
        assert admin_client.get(reverse("elo:ranking")).status_code == 200
        assert admin_client.get(reverse("dashboard:financial_overview")).status_code == 200


class TestPenaltyModuleOff:
    def test_penalty_pages_disappear(self, admin_client, modules):
        modules(["elo"])
        assert admin_client.get("/matchdays/").status_code == 404
        assert admin_client.get("/teams/").status_code == 404
        assert admin_client.get("/seasons/").status_code == 404
        assert admin_client.get(reverse("elo:ranking")).status_code == 200

    def test_elo_only_pages_render(self, admin_client, modules):
        modules(["elo"])
        for name in ("accounts:settings", "accounts:user_list", "audit_list", "overview"):
            assert admin_client.get(reverse(name)).status_code == 200, name

    def test_no_module_at_all(self, admin_client, modules):
        modules([])
        resp = admin_client.get("/", follow=True)
        assert resp.status_code == 200
        assert admin_client.get(reverse("accounts:settings")).status_code == 200

    def test_login_lands_on_the_start_page(self, client, admin_user, modules):
        modules(["elo"])
        resp = client.post(reverse("account_login"), {"login": admin_user.email, "password": "pw"})
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/"


class TestMembersWithoutPenalty:
    """Members belong to both modules: an Elo-only install keeps every member page."""

    def test_admin_member_pages(self, admin_client, player, modules):
        modules(["elo"])
        for url in ("/players/", "/players/create/", f"/players/{player.pk}/edit/"):
            assert admin_client.get(url).status_code == 200, url
        assert admin_client.get(reverse("accounts:user_list")).status_code == 200

    def test_profile_without_elo_leads_to_the_member_page(self, admin_client, player, modules):
        modules(["elo"])
        resp = admin_client.get(f"/players/{player.pk}/")
        assert resp.headers["Location"] == f"/players/{player.pk}/edit/"

    def test_profile_with_elo_leads_to_the_elo_page(self, admin_client, player, modules):
        from datetime import date

        from app.elo.models import EloProfile

        modules(["elo"])
        EloProfile.objects.create(
            player=player, start_elo=1500, current_elo=1500, entry_date=date(2026, 1, 1)
        )
        resp = admin_client.get(f"/players/{player.pk}/")
        assert resp.headers["Location"] == f"/elo/players/{player.pk}/"

    def test_captain_is_a_normal_account_without_penalty(self, captain_client, player, modules):
        modules(["elo"])
        assert captain_client.get("/players/create/").status_code == 403
        resp = captain_client.get(f"/players/{player.pk}/")
        assert resp.status_code in (302, 404)
        assert "/teams/" not in resp.headers.get("Location", "")


class TestEloModuleOff:
    def test_penalty_only_install(self, admin_client, modules):
        modules(["penalty"])
        assert admin_client.get("/elo/").status_code == 404
        assert admin_client.get("/").headers["Location"] == reverse("dashboard:financial_overview")
        html = admin_client.get(reverse("dashboard:financial_overview")).content.decode()
        assert "/elo/" not in html


class TestSiteName:
    def test_site_name_is_configurable(self, client, db):
        with override_settings(SITE_NAME="SV Musterstadt Darts"):
            html = client.get(reverse("account_login")).content.decode()
        assert "SV Musterstadt Darts" in html
        assert "Darts Penalty Manager" not in html
