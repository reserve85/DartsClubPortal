"""Importers of the old Elo and penalty databases."""

import json
import sqlite3
from datetime import date, timedelta

import pytest
from argon2 import PasswordHasher
from django.contrib.auth import get_user_model
from django.urls import reverse

from app.elo.models import EloProfile, Match
from app.elo.services.elo import calculate_match_elo
from app.importer.elo_import import import_elo
from app.importer.report import ImportAborted
from app.players.models import Player

User = get_user_model()
D0 = date(2025, 1, 10)


def make_elo_db(path, *, with_stale_value=False):
    """Minimal EloRankingSystem schema with consistent Elo snapshots."""
    con = sqlite3.connect(path)
    con.executescript(
        """
        create table users (id integer primary key, username text, password_hash text, role text,
            active boolean, created_at text, updated_at text, last_login_at text, must_change_password boolean);
        create table players (id integer primary key, name text, start_elo integer, current_elo float,
            active boolean, disabled boolean, last_match_date text, created_at text, updated_at text, entry_date text);
        create table player_disable_periods (id integer primary key, player_id integer, disabled_from text,
            disabled_to text, created_at text);
        create table matches (id integer primary key, date text, player_a_id integer, player_b_id integer,
            best_of_legs integer, player1_score integer, player2_score integer, winner_id integer, loser_id integer,
            elo_before_a float, elo_before_b float, elo_after_a float, elo_after_b float, elo_change_a float,
            elo_change_b float, player_a_180s integer, player_b_180s integer, player_a_high_finishes text,
            player_b_high_finishes text, player_a_low_darts text, player_b_low_darts text, created_by integer,
            created_at text, updated_at text, player_a_average float, player_b_average float, k_factor float);
        """
    )
    ph = PasswordHasher()
    con.executemany(
        "insert into users values (?,?,?,?,1,'2025-01-01 10:00:00','2025-01-01 10:00:00',null,0)",
        [
            (1, "system", ph.hash("sys"), "SYSTEM"),
            (2, "Dennis", ph.hash("admin-pw"), "ADMIN"),
            (3, "Wildboars", ph.hash("club-pw"), "USER"),
        ],
    )
    names = [(1, "Anna Beispiel", 1200), (2, "Bert", 1250), (3, "Carl", 1200)]
    games = [(1, 1, 2, 3, 1), (2, 2, 3, 3, 0), (3, 3, 1, 1, 3), (4, 1, 2, 2, 3)]
    elo = {pid: float(se) for pid, _n, se in names}
    rows = []
    for mid, a, b, sa, sb in games:
        r = calculate_match_elo(elo[a], elo[b], "A" if sa > sb else "B", 32)
        rows.append(
            (mid, (D0 + timedelta(days=mid)).isoformat(), a, b, 5, sa, sb, a if sa > sb else b,
             b if sa > sb else a, elo[a], elo[b], r.new_rating_a, r.new_rating_b, r.change_a,
             r.change_b, 1, 0, json.dumps([121] if sa > sb else []), "[]", "[]", "[]", 3,
             f"{(D0 + timedelta(days=mid)).isoformat()} 20:00:00", None, 55.5, 50.0, 32.0)
        )  # fmt: skip
        elo[a], elo[b] = r.new_rating_a, r.new_rating_b
    if with_stale_value:
        rows[-1] = (*rows[-1][:11], rows[-1][11] + 5, *rows[-1][12:])
    con.executemany("insert into matches values (" + ",".join("?" * 27) + ")", rows)
    con.executemany(
        "insert into players values (?,?,?,?,1,?,null,'2025-01-01 09:00:00',null,?)",
        [(pid, n, se, elo[pid], 1 if pid == 3 else 0, D0.isoformat()) for pid, n, se in names],
    )
    con.commit()
    con.close()
    return path


@pytest.mark.django_db
class TestEloImport:
    def test_full_import_matches_people_and_verifies(self, tmp_path, admin_user):
        Player.objects.create(name="anna beispiel")  # from the penalty system
        report = import_elo(
            make_elo_db(tmp_path / "elo.db"), account_map={"Dennis": admin_user.email}
        )
        assert report.ok, report.as_text()
        assert EloProfile.objects.count() == 3 and Match.objects.count() == 4
        assert Player.objects.filter(name__iexact="anna beispiel").count() == 1  # merged
        carl = EloProfile.objects.get(player__name="Carl")
        assert carl.disabled and carl.disable_periods.exists()
        m = Match.objects.order_by("date").first()
        assert m.a_high_finishes == [121] and m.a_average == 55.5
        # accounts: system skipped, Dennis linked, club account created Elo-only
        admin_user.refresh_from_db()
        assert admin_user.legacy_username == "Dennis"
        club = User.objects.get(legacy_username="Wildboars")
        assert club.check_password("club-pw")  # argon2 hash taken over
        assert club.elo_access and not club.penalty_access and not club.is_admin
        assert not User.objects.filter(legacy_username="system").exists()

    def test_dry_run_saves_nothing(self, tmp_path, db):
        report = import_elo(make_elo_db(tmp_path / "elo.db"), dry_run=True)
        assert report.ok and report.counts["matches imported"] == 4
        assert not Match.objects.exists() and not EloProfile.objects.exists()

    def test_second_import_needs_replace(self, tmp_path, db):
        path = make_elo_db(tmp_path / "elo.db")
        import_elo(path)
        with pytest.raises(ImportAborted):
            import_elo(path)
        report = import_elo(path, replace=True)
        assert report.ok and Match.objects.count() == 4

    def test_differences_to_the_old_system_are_reported(self, tmp_path, db):
        report = import_elo(make_elo_db(tmp_path / "elo.db", with_stale_value=True))
        assert not report.ok
        assert any(not ok for _l, ok, _d in report.checks)

    def test_wrong_file(self, tmp_path, db):
        bad = tmp_path / "x.db"
        bad.write_bytes(b"not a database")
        with pytest.raises(ImportAborted):
            import_elo(bad)


SEED_SOURCE = """
from datetime import date
from django.contrib.auth.models import Group
from app.accounts.models import User
from app.matchdays.models import Matchday, Season
from app.penalties.models import Penalty, PenaltyCatalogItem
from app.players.models import Player
from app.teams.models import Team
grp = Group.objects.get_or_create(name="Player")[0]
team = Team.objects.create(name="Wildboars 1")
season = Season.objects.create(name="2025/2026", is_default=True)
anna = Player.objects.create(name="Anna Beispiel")
u = User.objects.create(email="anna@example.com", approval_status="approved", player_link=anna)
u.groups.add(grp)
md = Matchday.objects.create(team=team, season=season, date=date(2025, 10, 1), opponent="SV X")
item = PenaltyCatalogItem.objects.create(description="Late", amount_eur=2)
Penalty.objects.create(matchday=md, player=anna, catalog_item=item, amount_eur=2)
"""
SEED_TARGET = 'from app.players.models import Player; Player.objects.create(name="anna beispiel")'


def _manage(db_path, *args):
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = dict(
        os.environ,
        SQLITE_PATH=str(db_path),
        EMAIL_BACKEND="django.core.mail.backends.dummy.EmailBackend",
    )
    root = Path(__file__).resolve().parent.parent
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=root,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=300,
    )


def test_penalty_import_end_to_end(tmp_path):
    """Real files: migrated penalty DB -> portal DB that already has a person."""
    source, target = tmp_path / "penalty.sqlite3", tmp_path / "portal.sqlite3"
    for db, seed in ((source, SEED_SOURCE), (target, SEED_TARGET)):
        assert _manage(db, "migrate", "-v", "0").returncode == 0
        res = _manage(db, "shell", "-c", seed)
        assert res.returncode == 0, res.stderr
    preview = _manage(target, "import_penalty", str(source), "--dry-run")
    assert preview.returncode == 0, preview.stderr
    con = sqlite3.connect(target)
    assert con.execute("select count(*) from penalties_penalty").fetchone()[0] == 0
    con.close()
    run = _manage(target, "import_penalty", str(source))
    assert run.returncode == 0, run.stdout + run.stderr
    con = sqlite3.connect(target)
    assert con.execute("select count(*) from players_player").fetchone()[0] == 1  # merged
    pid = con.execute(
        "select player_link_id from accounts_user where email='anna@example.com'"
    ).fetchone()[0]
    assert con.execute("select player_id from penalties_penalty").fetchone()[0] == pid
    con.close()


@pytest.mark.django_db
def test_import_page_is_admin_only(player_client, admin_client):
    assert player_client.get(reverse("importer:import")).status_code == 403
    assert admin_client.get(reverse("importer:import")).status_code == 200


@pytest.mark.django_db
def test_import_page_preview_and_run(admin_client, tmp_path, admin_user):
    path = make_elo_db(tmp_path / "elo.db")
    with open(path, "rb") as fh:
        resp = admin_client.post(
            reverse("importer:import"), {"action": "preview", "kind": "elo", "file": fh}
        )
    assert resp.status_code == 200 and not Match.objects.exists()
    resp = admin_client.post(
        reverse("importer:import"), {"action": "run", "map_2": str(admin_user.pk)}
    )
    assert resp.status_code == 200
    assert Match.objects.count() == 4
    admin_user.refresh_from_db()
    assert admin_user.legacy_username == "Dennis"
