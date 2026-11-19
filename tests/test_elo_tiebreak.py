"""Exact Elo ties in the ranking: head-to-head, legs, wins, then the name."""

import pytest

from app.elo.services.ranking import _ordered
from tests.test_elo_views import _play, elo_players  # noqa: F401


def _rows(*profiles, elo=1500.0):
    return [{"p": p, "end": elo} for p in profiles]


def _names(rows):
    return [r["p"].player.name for r in rows]


@pytest.mark.django_db
class TestTiebreak:
    def test_head_to_head_wins_first(self, elo_players):  # noqa: F811
        anna, bert, _carl = elo_players
        _play(bert, anna, 3, 1)  # Bert beat Anna
        assert _names(_ordered(_rows(anna, bert), "end", None)) == ["Bert", "Anna"]

    def test_then_legs_won_against_each_other(self, elo_players):  # noqa: F811
        anna, bert, _carl = elo_players
        _play(anna, bert, 3, 2)  # 1:1 in matches ...
        _play(bert, anna, 3, 0)  # ... legs: Bert 5, Anna 3
        assert _names(_ordered(_rows(anna, bert), "end", None)) == ["Bert", "Anna"]

    def test_then_all_wins(self, elo_players):  # noqa: F811
        anna, bert, carl = elo_players
        _play(bert, carl, 3, 0)  # no match between Anna and Bert
        assert _names(_ordered(_rows(anna, bert), "end", None)) == ["Bert", "Anna"]

    def test_finally_the_name(self, elo_players):  # noqa: F811
        anna, bert, _carl = elo_players
        assert _names(_ordered(_rows(bert, anna), "end", None)) == ["Anna", "Bert"]

    def test_higher_elo_always_wins(self, elo_players):  # noqa: F811
        anna, bert, _carl = elo_players
        _play(bert, anna, 3, 0)
        rows = [{"p": anna, "end": 1500.01}, {"p": bert, "end": 1500.0}]
        assert _names(_ordered(rows, "end", None)) == ["Anna", "Bert"]
