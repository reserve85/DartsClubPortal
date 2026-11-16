"""Elo pages, permissions, messaging (match mails + monthly summary),
unsubscribe links and QR login."""

import base64
import hashlib
import hmac
import json
from datetime import date, timedelta

import pytest
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from app.elo.models import EloMonthlyReport, Match
from app.elo.services import matches as match_service
from app.elo.services import players as player_service
from app.notifications.unsubscribe import make_token
from tests.conftest import inertia_props

TODAY = timezone.localdate()
D0 = TODAY - timedelta(days=200)


@pytest.fixture
def elo_players(db):
    return [
        player_service.add_to_ranking(name=n, start_elo=1200, entry_date=D0)
        for n in ("Anna", "Bert", "Carl")
    ]


@pytest.fixture
def linked_player_user(player_user, elo_players):
    player_user.player_link = elo_players[0].player
    player_user.save()
    return player_user


def _play(a, b, sa=3, sb=1, d=None, user=None):
    return match_service.create_match(
        player_a=a.player,
        player_b=b.player,
        match_date=d or TODAY,
        score_a=sa,
        score_b=sb,
        user=user,
    )


def _post_match(client, a, b, sa=3, sb=1, **extra):
    data = {
        "player_a": a.player_id,
        "player_b": b.player_id,
        "match_date": TODAY.isoformat(),
        "best_of_legs": 5,
        "score_a": sa,
        "score_b": sb,
        **extra,
    }
    return client.post(reverse("elo:match_create"), data)


# ----------------------------------------------------------------- pages
@pytest.mark.django_db
class TestPages:
    def test_every_page_renders_for_a_member(self, player_client, elo_players):
        a, b, _c = elo_players
        m = _play(a, b)
        urls = [
            reverse("elo:ranking"),
            reverse("elo:ranking") + "?period=year&inactive=1",
            reverse("elo:ranking") + "?period=custom&from=2020-01-01&to=2030-01-01",
            reverse("elo:all_time"),
            reverse("elo:match_list"),
            reverse("elo:match_list") + f"?player={a.player_id}&from=2020-01-01",
            reverse("elo:match_create"),
            reverse("elo:match_detail", args=[m.pk]),
            reverse("elo:player_detail", args=[a.player_id]),
            reverse("elo:player_detail", args=[a.player_id]) + "?period=all",
            reverse("elo:h2h"),
            reverse("elo:h2h") + f"?a={a.player_id}",
            reverse("elo:h2h") + f"?a={a.player_id}&b={b.player_id}",
            reverse("overview"),
        ]
        for url in urls:
            assert player_client.get(url).status_code == 200, url

    def test_empty_ranking_renders(self, player_client, db):
        assert player_client.get(reverse("elo:ranking")).status_code == 200

    def test_ranking_marks_my_row(self, player_client, linked_player_user, elo_players):
        _play(elo_players[0], elo_players[1])
        props = inertia_props(player_client.get(reverse("elo:ranking")))
        assert props["myPlayerId"] == elo_players[0].player_id

    def test_inverted_custom_range_is_rejected_gracefully(self, player_client, elo_players):
        resp = player_client.get(
            reverse("elo:ranking") + "?period=custom&from=2030-01-01&to=2020-01-01"
        )
        assert resp.status_code == 200  # swapped and clamped, never an error
        period = inertia_props(resp)["period"]
        assert period["from"] <= period["to"] <= timezone.localdate().isoformat()


# ------------------------------------------------------------ permissions
@pytest.mark.django_db
class TestPermissions:
    def test_members_enter_but_cannot_edit_or_manage(self, player_client, elo_players):
        a, b, _c = elo_players
        resp = _post_match(player_client, a, b)
        assert resp.status_code == 302
        m = Match.objects.get()
        for name, args in (
            ("elo:match_update", [m.pk]),
            ("elo:match_delete", [m.pk]),
            ("elo:manage", []),
            ("elo:player_add", []),
            ("elo:player_edit", [a.player_id]),
            ("elo:export_matches", []),
        ):
            assert player_client.get(reverse(name, args=args)).status_code == 403, name
        assert player_client.post(reverse("elo:recalculate")).status_code == 403
        assert player_client.post(reverse("elo:match_delete", args=[m.pk])).status_code == 403
        assert Match.objects.count() == 1

    def test_captains_are_no_elo_admins(self, captain_client, elo_players):
        assert captain_client.get(reverse("elo:manage")).status_code == 403
        assert captain_client.post(reverse("elo:recalculate")).status_code == 403

    def test_anonymous_is_sent_to_login(self, client, elo_players):
        resp = client.get(reverse("elo:ranking"))
        assert resp.status_code == 302 and "login" in resp.headers["Location"]

    def test_admin_edits_and_deletes(self, admin_client, elo_players):
        a, b, _c = elo_players
        m = _play(a, b)
        resp = admin_client.post(
            reverse("elo:match_update", args=[m.pk]),
            {"match_date": TODAY.isoformat(), "best_of_legs": 5, "score_a": 0, "score_b": 3},
        )
        assert resp.status_code == 302
        m.refresh_from_db()
        assert m.winner_id == b.player_id
        assert admin_client.post(reverse("elo:match_delete", args=[m.pk])).status_code == 302
        assert not Match.objects.exists()

    def test_admin_manages_players_and_exports(self, admin_client, elo_players):
        a, b, _c = elo_players
        _play(a, b)
        assert admin_client.get(reverse("elo:manage")).status_code == 200
        resp = admin_client.post(
            reverse("elo:player_add"),
            {"name": "Dora", "start_elo": 1300, "entry_date": TODAY.isoformat()},
        )
        assert resp.status_code == 302
        resp = admin_client.post(
            reverse("elo:player_edit", args=[a.player_id]),
            {"name": "Anna B.", "start_elo": 1250, "entry_date": D0.isoformat()},
        )
        assert resp.status_code == 302
        a.refresh_from_db()
        assert a.player.name == "Anna B." and a.start_elo == 1250
        assert (
            admin_client.post(reverse("elo:player_toggle", args=[b.player_id])).status_code == 302
        )
        b.refresh_from_db()
        assert b.disabled
        for name in ("export_matches", "export_players", "export_ranking"):
            resp = admin_client.get(reverse(f"elo:{name}"))
            assert resp.status_code == 200 and resp["Content-Type"].startswith("text/csv")
        assert admin_client.post(reverse("elo:recalculate")).status_code == 302


# ------------------------------------------------------------ match entry
@pytest.mark.django_db
class TestMatchEntry:
    def test_duplicate_needs_confirmation(self, player_client, elo_players):
        a, b, _c = elo_players
        _post_match(player_client, a, b)
        resp = _post_match(player_client, a, b)
        assert resp.status_code == 200
        assert inertia_props(resp)["duplicate"] is True
        assert Match.objects.count() == 1
        resp = _post_match(player_client, a, b, force="True")
        assert resp.status_code == 302
        assert Match.objects.count() == 2

    def test_invalid_score_shows_error(self, player_client, elo_players):
        a, b, _c = elo_players
        resp = _post_match(player_client, a, b, sa=3, sb=3)
        assert resp.status_code == 200
        assert not Match.objects.exists()

    def test_save_and_next_keeps_player_a(self, player_client, elo_players):
        a, b, _c = elo_players
        resp = _post_match(player_client, a, b, again="1")
        assert resp.headers["Location"].endswith(f"?a={a.player_id}")

    def test_statistics_are_saved(self, player_client, elo_players):
        a, b, _c = elo_players
        _post_match(
            player_client,
            a,
            b,
            sa=3,
            sb=2,
            a_180s=1,
            a_high_finishes="121, 100",
            b_low_darts="15",
            a_average="55.5",
        )
        m = Match.objects.get()
        assert m.a_180s == 1 and m.a_high_finishes == [121, 100] and m.b_low_darts == [15]
        assert m.a_average == 55.5


# ------------------------------------------------------------- messaging
@pytest.mark.django_db
class TestMessaging:
    def test_opponent_gets_inapp_and_mail_but_not_the_actor(
        self, admin_client, admin_user, linked_player_user, elo_players
    ):
        from notifications.models import Notification

        a, b, _c = elo_players
        _post_match(admin_client, b, a, sa=3, sb=0)  # Anna (linked) lost
        assert Notification.objects.filter(recipient=linked_player_user).count() == 1
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        assert "/notifications/actions/unsubscribe/" in body
        assert linked_player_user.email in mail.outbox[0].to

    def test_mail_switched_off(self, admin_client, linked_player_user, elo_players):
        linked_player_user.elo_match_notify = False
        linked_player_user.save()
        _post_match(admin_client, elo_players[1], elo_players[0])
        assert len(mail.outbox) == 0

    def test_daily_summary_collects_the_matches_into_one_mail(
        self, admin_client, linked_player_user, elo_players
    ):
        from datetime import timedelta

        from django.utils import timezone

        from app.elo.models import EloMailQueue
        from app.elo.notify import flush_elo_digests

        linked_player_user.elo_match_digest = True
        linked_player_user.save()
        a, b, c = elo_players
        _post_match(admin_client, b, a, sa=3, sb=0)
        _post_match(admin_client, a, c, sa=3, sb=1)
        assert len(mail.outbox) == 0  # nothing right away
        assert EloMailQueue.objects.filter(user=linked_player_user).count() == 2
        assert flush_elo_digests() == 0  # not due before the digest time
        assert flush_elo_digests(now=timezone.now() + timedelta(days=1, hours=1)) == 1
        assert len(mail.outbox) == 1  # ONE mail for both matches
        body = mail.outbox[0].body
        assert body.count(b.name) >= 1 and body.count(c.name) >= 1
        assert "/notifications/actions/unsubscribe/" in body
        assert not EloMailQueue.objects.exists()

    def test_daily_summary_dropped_when_switched_off_meanwhile(
        self, admin_client, linked_player_user, elo_players
    ):
        from datetime import timedelta

        from django.utils import timezone

        from app.elo.models import EloMailQueue
        from app.elo.notify import flush_elo_digests

        linked_player_user.elo_match_digest = True
        linked_player_user.save()
        _post_match(admin_client, elo_players[1], elo_players[0])
        linked_player_user.elo_match_notify = False
        linked_player_user.save()
        assert flush_elo_digests(now=timezone.now() + timedelta(days=2)) == 0
        assert len(mail.outbox) == 0 and not EloMailQueue.objects.exists()

    def test_own_entry_sends_nothing_to_me(self, player_client, linked_player_user, elo_players):
        _post_match(player_client, elo_players[0], elo_players[1])
        assert len(mail.outbox) == 0

    def test_monthly_summary_once_per_month(self, linked_player_user, elo_players):
        from app.elo.notify import maybe_send_monthly, previous_month, send_monthly_summaries

        start, _end = previous_month()
        a, b, _c = elo_players
        _play(a, b, d=max(start, D0))
        sent = send_monthly_summaries(month_start=start)
        assert sent == 1 and len(mail.outbox) == 1
        assert "unsubscribe" in mail.outbox[0].body
        assert send_monthly_summaries(month_start=start) == 0  # never twice
        assert EloMonthlyReport.objects.filter(month=start).exists()
        first = timezone.make_aware(timezone.datetime(TODAY.year, TODAY.month, 1, 9, 0))
        assert maybe_send_monthly(first) == 0  # already sent

    def test_monthly_summary_respects_opt_out(self, linked_player_user, elo_players):
        from app.elo.notify import previous_month, send_monthly_summaries

        linked_player_user.elo_monthly_summary = False
        linked_player_user.save()
        start, _end = previous_month()
        assert send_monthly_summaries(month_start=start) == 0

    def test_due_window(self):
        from app.elo.notify import monthly_summary_due

        tz = timezone.get_current_timezone()
        assert not monthly_summary_due(timezone.datetime(2026, 11, 1, 7, 59, tzinfo=tz))
        assert monthly_summary_due(timezone.datetime(2026, 11, 1, 8, 0, tzinfo=tz))
        assert monthly_summary_due(timezone.datetime(2026, 11, 3, 23, 0, tzinfo=tz))
        assert not monthly_summary_due(timezone.datetime(2026, 11, 4, 9, 0, tzinfo=tz))


@pytest.mark.django_db
class TestUnsubscribe:
    @pytest.mark.parametrize(
        "kind,field,off",
        [
            ("elo_match", "elo_match_notify", False),
            ("elo_monthly", "elo_monthly_summary", False),
            ("repayment", "repayment_notify", False),
            ("news", "club_news_optin", False),
            ("penalty", "penalty_notify_mode", "off"),
        ],
    )
    def test_one_click_without_login(self, client, player_user, kind, field, off):
        url = reverse("notifications_manage:unsubscribe", args=[make_token(player_user, kind)])
        assert client.get(url).status_code == 200
        player_user.refresh_from_db()
        assert getattr(player_user, field) != off  # GET never unsubscribes (mail prefetch)
        assert client.post(url).status_code == 200
        player_user.refresh_from_db()
        assert getattr(player_user, field) == off

    def test_tampered_token(self, client, player_user):
        url = reverse("notifications_manage:unsubscribe", args=["broken"])
        assert client.post(url).status_code == 200
        player_user.refresh_from_db()
        assert player_user.elo_match_notify


# --------------------------------------------------------------- QR login
@pytest.mark.django_db
class TestQrLogin:
    def test_admin_prints_code_and_member_logs_in(self, admin_client, player_user):
        from app.accounts.qr import make_token as qr_token

        page = admin_client.get(reverse("accounts:user_qr", args=[player_user.pk]))
        assert page.status_code == 200 and "data:image/png;base64," in page.content.decode()
        c = Client()
        resp = c.post(reverse("accounts:qr_login"), {"token": qr_token(player_user)})
        assert resp.status_code == 200 and "redirect" in resp.json()
        assert c.get(reverse("accounts:settings")).status_code == 200

    def test_password_change_invalidates_codes(self, player_user):
        from app.accounts.qr import make_token as qr_token

        token = qr_token(player_user)
        player_user.set_password("new-pw-123!")
        player_user.save()
        resp = Client().post(reverse("accounts:qr_login"), {"token": token})
        assert resp.status_code == 401

    def test_admins_never_by_qr(self, admin_user):
        from app.accounts.qr import make_token as qr_token

        resp = Client().post(reverse("accounts:qr_login"), {"token": qr_token(admin_user)})
        assert resp.status_code == 401

    def test_members_cannot_print_codes(self, player_client, player_user):
        assert (
            player_client.get(reverse("accounts:user_qr", args=[player_user.pk])).status_code == 403
        )

    def test_legacy_password_url(self, player_user, settings):
        player_user.legacy_username = "kneipe"
        player_user.save()
        c = Client()
        resp = c.get("/auth/auto-login", {"u": "kneipe", "p": "pw"})
        assert resp.status_code == 302 and "login" not in resp.headers["Location"]
        bad = Client().get("/auth/auto-login", {"u": "kneipe", "p": "wrong"})
        assert "login" in bad.headers["Location"]
        settings.ELO_LEGACY_QR_LOGIN = False
        off = Client().get("/auth/auto-login", {"u": "kneipe", "p": "pw"})
        assert "login" in off.headers["Location"]

    def test_legacy_jwt_token(self, player_user, settings):
        secret = "old-elo-secret"
        settings.ELO_LEGACY_JWT_SECRET = secret
        elo_hash = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHQ$aGFzaGhhc2hoYXNo"
        player_user.password = "argon2" + elo_hash
        player_user.legacy_elo_id = 7
        player_user.save()

        def b64(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        pwv = hmac.new(secret.encode(), elo_hash.encode(), hashlib.sha256).hexdigest()[:32]
        head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        body = b64(json.dumps({"sub": "7", "purpose": "qr", "pwv": pwv}).encode())
        sig = b64(hmac.new(secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest())
        token = f"{head}.{body}.{sig}"
        assert Client().get("/ui/qr-login").status_code == 200
        ok = Client().post(reverse("accounts:qr_login"), {"token": token, "legacy": "1"})
        assert ok.status_code == 200
        forged = Client().post(
            reverse("accounts:qr_login"), {"token": token[:-2] + "xx", "legacy": "1"}
        )
        assert forged.status_code == 401


@pytest.mark.django_db
def test_settings_save_start_page_and_elo_mails(player_client, player_user):
    resp = player_client.post(
        reverse("accounts:settings"),
        {
            "preferred_language": "de",
            "preferred_theme": "dark",
            "start_page": "overview",
            "penalty_notify_mode": "daily",
            "penalty_notify_time": "08:00",
            "repayment_notify": "True",
            "club_news_optin": "False",
            "elo_match_notify": "False",
            "elo_monthly_summary": "True",
        },
    )
    assert resp.status_code == 302
    player_user.refresh_from_db()
    assert player_user.start_page == "overview"
    assert player_user.elo_match_notify is False and player_user.elo_monthly_summary is True


@pytest.mark.django_db
def test_admin_sets_module_access(admin_client, player_user, role_groups):
    resp = admin_client.post(
        reverse("accounts:user_update", args=[player_user.pk]),
        {
            "email": player_user.email,
            "role": "Player",
            "is_active": "on",
            "preferred_language": "de",
            "elo_access": "on",
        },
    )
    assert resp.status_code == 302
    player_user.refresh_from_db()
    assert player_user.elo_access and not player_user.penalty_access


def test_date_helpers_month_edges():
    from app.elo.notify import previous_month

    assert previous_month(date(2026, 3, 15)) == (date(2026, 2, 1), date(2026, 2, 28))
    assert previous_month(date(2026, 1, 1)) == (date(2025, 12, 1), date(2025, 12, 31))


@pytest.mark.django_db
def test_react_json_post_creates_match(player_client, elo_players):
    """The React page posts JSON with the Inertia header (InertiaJsonFormMiddleware)."""
    import json as _json

    a, b, _c = elo_players
    payload = {
        "player_a": a.player_id,
        "player_b": b.player_id,
        "match_date": TODAY.isoformat(),
        "best_of_legs": 5,
        "score_a": 3,
        "score_b": 2,
        "a_180s": 1,
        "b_180s": "",
        "a_high_finishes": "121",
        "b_high_finishes": "",
        "a_low_darts": "",
        "b_low_darts": "15",
        "a_average": 55.5,
        "b_average": None,
        "force": False,
        "again": False,
    }
    resp = player_client.post(
        reverse("elo:match_create"),
        data=_json.dumps(payload),
        content_type="application/json",
        HTTP_X_INERTIA="true",
    )
    assert resp.status_code in (302, 303)
    assert "/elo/matches/" in resp.headers["Location"] and "?a=" not in resp.headers["Location"]
    m = Match.objects.get()
    assert (m.score_a, m.score_b, m.a_180s, m.a_high_finishes, m.b_low_darts, m.a_average) == (
        3,
        2,
        1,
        [121],
        [15],
        55.5,
    )
