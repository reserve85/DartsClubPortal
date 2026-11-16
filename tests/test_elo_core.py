"""Elo core: formula, match validation, timeline recalculation, ranking,
statistics, best rank and head-to-head (ported rules from EloRankingSystem)."""

import random
from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from app.core.models import AuditAction, AuditLog
from app.elo.models import EloProfile, Match
from app.elo.services import h2h, matches, players, ranking
from app.elo.services.elo import calculate_expected_score, calculate_match_elo
from app.elo.services.validation import determine_winner, valid_scores

TODAY = timezone.localdate()
D0 = TODAY - timedelta(days=400)


def mk(name, start=1200, entry=D0):
    return players.add_to_ranking(name=name, start_elo=start, entry_date=entry)


def play(a, b, sa, sb, d, **kw):
    return matches.create_match(
        player_a=a.player, player_b=b.player, match_date=d, score_a=sa, score_b=sb, **kw
    )


def reload(*profiles):
    for p in profiles:
        p.refresh_from_db()


def full_replay() -> dict[int, float]:
    """Reference: replay every match from scratch, independent of the service."""
    elo = {p.player_id: float(p.start_elo) for p in EloProfile.objects.all()}
    for m in Match.objects.order_by("date", "created_at", "id"):
        r = calculate_match_elo(
            elo[m.player_a_id],
            elo[m.player_b_id],
            "A" if m.winner_id == m.player_a_id else "B",
            m.k_factor,
        )
        assert m.elo_before_a == pytest.approx(elo[m.player_a_id])
        assert m.elo_before_b == pytest.approx(elo[m.player_b_id])
        elo[m.player_a_id], elo[m.player_b_id] = r.new_rating_a, r.new_rating_b
        assert m.elo_after_a == pytest.approx(r.new_rating_a)
        assert m.elo_after_b == pytest.approx(r.new_rating_b)
    return elo


# --------------------------------------------------------------------- formula
class TestFormula:
    def test_equal_ratings_split_k(self):
        r = calculate_match_elo(1200, 1200, "A", 32)
        assert r.change_a == pytest.approx(16)
        assert r.change_b == pytest.approx(-16)

    def test_expected_score_400_points(self):
        assert calculate_expected_score(1600, 1200) == pytest.approx(10 / 11)

    def test_zero_sum(self):
        r = calculate_match_elo(1432.5, 1187.25, "B", 32)
        assert r.change_a + r.change_b == pytest.approx(0)

    def test_invalid_winner(self):
        with pytest.raises(ValueError):
            calculate_match_elo(1200, 1200, "X")

    @pytest.mark.parametrize(
        "bo,scores",
        [(1, {(1, 0), (0, 1)}), (5, {(3, 0), (3, 1), (3, 2), (0, 3), (1, 3), (2, 3)})],
    )
    def test_valid_scores(self, bo, scores):
        assert valid_scores(bo) == scores

    @pytest.mark.parametrize("sa,sb,bo", [(3, 3, 5), (2, 1, 5), (4, 0, 5), (3, 0, 4)])
    def test_invalid_scores(self, sa, sb, bo):
        with pytest.raises(ValidationError):
            determine_winner(sa, sb, bo)


# -------------------------------------------------------------------- matches
@pytest.mark.django_db
class TestMatchEntry:
    def test_create_updates_both_players_and_audits(self):
        a, b = mk("Anna"), mk("Bert")
        m = play(a, b, 3, 1, D0 + timedelta(days=1))
        reload(a, b)
        assert m.winner_id == a.player_id
        assert a.current_elo == pytest.approx(1216)
        assert b.current_elo == pytest.approx(1184)
        assert a.active and b.active and a.last_match_date == m.date
        assert AuditLog.objects.filter(action=AuditAction.ELO_MATCH_CREATED).count() == 1

    def test_rejections(self):
        a, b, c = mk("Anna"), mk("Bert"), mk("Carl")
        d = D0 + timedelta(days=1)
        with pytest.raises(ValidationError):
            play(a, a, 3, 0, d)
        with pytest.raises(ValidationError):
            play(a, b, 3, 3, d)
        with pytest.raises(ValidationError):
            play(a, b, 3, 0, TODAY + timedelta(days=1))
        with pytest.raises(ValidationError):
            play(a, b, 3, 0, D0 - timedelta(days=1))  # before entry date
        players.disable(c)
        with pytest.raises(ValidationError):
            play(a, c, 3, 0, d)
        assert Match.objects.count() == 0

    def test_duplicate_needs_force(self):
        a, b = mk("Anna"), mk("Bert")
        d = D0 + timedelta(days=1)
        play(a, b, 3, 1, d)
        with pytest.raises(matches.DuplicateMatchError):
            play(b, a, 1, 3, d)  # same result seen from the other side
        play(a, b, 3, 1, d, force=True)
        assert Match.objects.count() == 2

    def test_statistics_plausibility(self):
        a, b = mk("Anna"), mk("Bert")
        d = D0 + timedelta(days=1)
        with pytest.raises(ValidationError):
            play(a, b, 3, 1, d, stats={"a_high_finishes": [169]})  # impossible
        with pytest.raises(ValidationError):
            play(a, b, 3, 1, d, stats={"b_high_finishes": [120, 121]})  # B won 1 leg
        with pytest.raises(ValidationError):
            play(a, b, 3, 0, d, stats={"a_180s": 10})  # > 3 per leg
        with pytest.raises(ValidationError):
            play(a, b, 3, 0, d, stats={"a_low_darts": [8]})
        m = play(
            a,
            b,
            3,
            2,
            d,
            stats={
                "a_180s": 2,
                "a_high_finishes": [121, 170],
                "b_low_darts": [15],
                "a_average": 61.5,
            },
        )
        assert m.a_high_finishes == [121, 170] and m.a_average == 61.5

    def test_best_of_formats(self):
        a, b = mk("Anna"), mk("Bert")
        m = play(a, b, 6, 4, D0 + timedelta(days=1), best_of_legs=11)
        assert m.best_of_legs == 11
        with pytest.raises(ValidationError):
            play(a, b, 3, 1, D0 + timedelta(days=2), best_of_legs=4)


@pytest.mark.django_db
class TestRecalculation:
    def test_backdated_match_replays_later_ones(self):
        a, b = mk("Anna"), mk("Bert")
        later = play(a, b, 3, 0, D0 + timedelta(days=10))
        play(b, a, 3, 0, D0 + timedelta(days=5))  # earlier, inserted afterwards
        later.refresh_from_db()
        assert later.elo_before_a == pytest.approx(1184)  # Anna lost the earlier one
        full_replay()

    def test_edit_flips_winner(self):
        a, b = mk("Anna"), mk("Bert")
        m = play(a, b, 3, 0, D0 + timedelta(days=1))
        matches.update_match(m, score_a=1, score_b=3)
        reload(a, b)
        assert b.current_elo == pytest.approx(1216)
        assert AuditLog.objects.filter(action=AuditAction.ELO_MATCH_UPDATED).exists()
        full_replay()

    def test_delete_last_match_resets_player(self):
        a, b = mk("Anna", start=1300), mk("Bert")
        m = play(a, b, 3, 0, D0 + timedelta(days=1))
        matches.delete_match(m)
        reload(a, b)
        assert a.current_elo == 1300 and b.current_elo == 1200
        assert not a.active and a.last_match_date is None

    def test_other_players_keep_pre_window_rating(self):
        a, b, c = mk("Anna"), mk("Bert"), mk("Carl")
        play(b, c, 3, 0, D0 + timedelta(days=1))  # Bert 1216 before the window
        play(a, c, 3, 0, D0 + timedelta(days=5))
        m = play(a, b, 3, 0, D0 + timedelta(days=6))
        assert m.elo_before_b == pytest.approx(1216)
        matches.update_match(m, score_a=0, score_b=3)  # window starts at Anna's first match
        full_replay()

    def test_start_elo_change_replays(self):
        a, b = mk("Anna"), mk("Bert")
        play(a, b, 3, 0, D0 + timedelta(days=1))
        players.update_profile(a, start_elo=1400)
        reload(a)
        assert a.current_elo == pytest.approx(
            1400 + 32 * (1 - calculate_expected_score(1400, 1200))
        )
        full_replay()

    def test_entry_date_cannot_pass_first_match(self):
        a, b = mk("Anna"), mk("Bert")
        play(a, b, 3, 0, D0 + timedelta(days=3))
        with pytest.raises(ValidationError):
            players.update_profile(a, entry_date=D0 + timedelta(days=4))

    def test_random_operations_always_equal_a_full_replay(self):
        rnd = random.Random(42)
        profs = [mk(f"P{i:02d}", start=1100 + 25 * i) for i in range(8)]
        for _ in range(120):
            op = rnd.random()
            existing = list(Match.objects.all())
            if op < 0.65 or not existing:
                a, b = rnd.sample(profs, 2)
                sa, sb = rnd.choice(sorted(valid_scores(5)))
                play(a, b, sa, sb, D0 + timedelta(days=rnd.randint(0, 300)), force=True)
            elif op < 0.85:
                m = rnd.choice(existing)
                sa, sb = rnd.choice(sorted(valid_scores(5)))
                matches.update_match(
                    m,
                    score_a=sa,
                    score_b=sb,
                    match_date=D0 + timedelta(days=rnd.randint(0, 300)),
                    force=True,
                )
            else:
                matches.delete_match(rnd.choice(existing))
        elo = full_replay()
        for p in EloProfile.objects.all():
            assert p.current_elo == pytest.approx(elo[p.player_id])
        before = {m.pk: m.elo_after_a for m in Match.objects.all()}
        matches.recalculate_all()
        assert {m.pk: m.elo_after_a for m in Match.objects.all()} == pytest.approx(before)


# -------------------------------------------------------------------- ranking
@pytest.mark.django_db
class TestRanking:
    def test_full_field_positions_and_hidden_rows(self):
        a, b = mk("Anna"), mk("Bert")
        mk("Carl", start=1250)
        d = TODAY
        play(a, b, 3, 0, d)
        shown = ranking.generate_ranking(d, TODAY)
        full = ranking.generate_ranking(d, TODAY, include_inactive=True)
        assert [e.name for e in full.entries] == ["Carl", "Anna", "Bert"] or [
            e.name for e in full.entries
        ] == ["Anna", "Carl", "Bert"]
        names = [e.name for e in shown.entries]
        assert "Carl" not in names  # never played -> hidden, but keeps its slot
        pos = {e.name: e.position for e in full.entries}
        assert {e.name: e.position for e in shown.entries} == {n: pos[n] for n in names}
        assert next(e for e in full.entries if e.name == "Carl").position_change is None

    def test_period_change_and_statistics(self):
        a, b = mk("Anna"), mk("Bert")
        play(a, b, 3, 0, D0 + timedelta(days=1), stats={"a_180s": 1})
        start = D0 + timedelta(days=2)
        play(b, a, 3, 1, start + timedelta(days=1), stats={"a_180s": 2, "a_high_finishes": [100]})
        r = ranking.generate_ranking(start, start + timedelta(days=5), include_inactive=True)
        bert = next(e for e in r.entries if e.name == "Bert")
        assert bert.matches == 1 and bert.total_180s == 2 and bert.high_finishes == [100]
        assert bert.elo_change > 0

    def test_disabled_stay_in_field(self):
        a, b, c = mk("Anna"), mk("Bert"), mk("Carl")
        d = TODAY - timedelta(days=1)
        play(c, a, 3, 0, d)
        play(b, a, 3, 0, d)
        players.disable(c)
        r = ranking.generate_ranking(include_inactive=False)
        assert "Carl" not in [e.name for e in r.entries]
        assert r.field_size == 3

    def test_inactivity_cutoff_month_end(self, settings):
        settings.ELO = {"INACTIVITY_MONTHS": 3}
        assert ranking.inactive_cutoff(date(2026, 5, 31)) == date(2026, 2, 28)
        assert ranking.is_inactive(date(2026, 2, 27), date(2026, 5, 31))
        assert not ranking.is_inactive(date(2026, 2, 28), date(2026, 5, 31))

    def test_inverted_range(self):
        with pytest.raises(ValidationError):
            ranking.generate_ranking(TODAY, TODAY - timedelta(days=1))

    def test_ath_best_rank_and_stats(self):
        a, b, c = mk("Anna"), mk("Bert"), mk("Carl")
        play(a, b, 3, 0, D0 + timedelta(days=1), stats={"a_average": 50})
        play(a, c, 3, 0, D0 + timedelta(days=2), stats={"a_average": 60})
        play(b, a, 3, 0, D0 + timedelta(days=3))
        ath = ranking.all_time_high_elo(a)
        assert ath["date_reached"] == D0 + timedelta(days=2)
        assert ranking.best_rank(a.player_id) == {
            "best_rank": 1,
            "date_reached": D0 + timedelta(days=1),
        }
        st = ranking.player_statistics(a.player_id)
        assert st["all_time"]["wins"] == 2 and st["all_time"]["losses"] == 1
        assert st["all_time"]["average"] == 55 and st["all_time"]["average_last100"] == 55
        assert len(ranking.elo_history(a.player_id)) == 3
        top = next(iter(ranking.all_players_all_time_high(include_inactive=True)))
        assert top["name"] == "Anna"


# ------------------------------------------------------------- head-to-head
@pytest.mark.django_db
class TestHeadToHead:
    def test_summary_streak_and_probability(self):
        a, b, c = mk("Anna", start=1400), mk("Bert"), mk("Carl")
        for i, (sa, sb) in enumerate([(3, 0), (1, 3), (3, 2), (3, 1)]):
            play(a, b, sa, sb, D0 + timedelta(days=i + 1), stats={"a_average": 50 + i})
        play(a, c, 3, 0, D0 + timedelta(days=9))
        res = h2h.head_to_head(a.player_id, b.player_id)
        assert res["total_matches"] == 4
        assert res["a"]["wins"] == 3 and res["b"]["wins"] == 1
        assert res["streak"] == {"player_id": a.player_id, "count": 2}
        assert res["win_probability_a"] + res["win_probability_b"] == pytest.approx(1)
        assert res["a"]["elo_net"] == pytest.approx(-res["b"]["elo_net"], abs=0.02)
        assert res["timeline"][-1]["elo_balance_a"] == pytest.approx(res["a"]["elo_net"], abs=0.02)
        opp = h2h.opponents(a.player_id)
        assert [o["name"] for o in opp] == ["Bert", "Carl"]

    def test_same_player(self):
        a = mk("Anna")
        with pytest.raises(ValidationError):
            h2h.head_to_head(a.player_id, a.player_id)


@pytest.mark.django_db
class TestPlayers:
    def test_unique_names_and_existing_person(self):
        from app.players.models import Player

        mk("Anna")
        with pytest.raises(ValidationError):
            mk("anna")
        person = Player.objects.create(name="Dora")
        prof = players.add_to_ranking(player=person, start_elo=1300)
        assert prof.player_id == person.pk and prof.current_elo == 1300
        with pytest.raises(ValidationError):
            players.add_to_ranking(player=person)

    def test_disable_period_trail(self):
        a = mk("Anna")
        players.disable(a)
        players.reactivate(a)
        period = a.disable_periods.get()
        assert period.disabled_to == TODAY
