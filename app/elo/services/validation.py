"""Score and dart-statistics validation for matches."""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from app.elo.conf import elo_setting

# Finishes that cannot be checked out with three darts.
IMPOSSIBLE_HIGH_FINISHES = frozenset({169, 168, 166, 165, 163, 162, 159})
# Valid match formats: best of an odd number of legs.
VALID_BEST_OF = (1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21)
# At most three 180s per leg played (two are possible in 501, one spare).
MAX_180S_PER_LEG = 3


def wins_needed(best_of: int) -> int:
    return (best_of + 1) // 2


def valid_scores(best_of: int) -> set[tuple[int, int]]:
    need = wins_needed(best_of)
    scores = set()
    for loser in range(need):
        scores.add((need, loser))
        scores.add((loser, need))
    return scores


def validate_best_of(best_of: int) -> int:
    if best_of not in VALID_BEST_OF:
        raise ValidationError(
            _("The format must be best of %(values)s legs."),
            params={"values": ", ".join(str(v) for v in VALID_BEST_OF)},
            code="best_of",
        )
    return best_of


def determine_winner(score_a: int, score_b: int, best_of: int) -> str:
    """'A' or 'B' - raises ValidationError when the score does not fit the format."""
    validate_best_of(best_of)
    if (score_a, score_b) not in valid_scores(best_of):
        raise ValidationError(
            _("%(a)s:%(b)s is not a valid result for best of %(n)s legs."),
            params={"a": score_a, "b": score_b, "n": best_of},
            code="score",
        )
    return "A" if score_a > score_b else "B"


def _check_values(values, label, lo, hi, impossible=None):
    for val in values or []:
        if not isinstance(val, int) or isinstance(val, bool):
            raise ValidationError(_("%(label)s: only whole numbers."), params={"label": label})
        if val < lo or val > hi:
            raise ValidationError(
                _("%(label)s %(value)s is outside %(lo)s-%(hi)s."),
                params={"label": label, "value": val, "lo": lo, "hi": hi},
                code="range",
            )
        if impossible and val in impossible:
            raise ValidationError(
                _("%(label)s %(value)s cannot be checked out with three darts."),
                params={"label": label, "value": val},
                code="impossible",
            )


def validate_statistics(a_hf, b_hf, a_ld, b_ld) -> None:
    hf_lo, hf_hi = elo_setting("HIGH_FINISH_MIN"), elo_setting("HIGH_FINISH_MAX")
    ld_lo, ld_hi = elo_setting("LOW_DARTS_MIN"), elo_setting("LOW_DARTS_MAX")
    for values in (a_hf, b_hf):
        _check_values(values, _("High finish"), hf_lo, hf_hi, IMPOSSIBLE_HIGH_FINISHES)
    for values in (a_ld, b_ld):
        _check_values(values, _("Low darts"), ld_lo, ld_hi)


def validate_statistics_against_score(score_a, score_b, a_180s, b_180s, a_hf, b_hf, a_ld, b_ld):
    """High finishes / low-darts legs <= legs won; 180s <= 3 per leg played."""
    legs_played = (score_a or 0) + (score_b or 0)
    for label, won, n180, hf, ld in (
        (_("Player A"), score_a or 0, a_180s, a_hf, a_ld),
        (_("Player B"), score_b or 0, b_180s, b_hf, b_ld),
    ):
        if hf and len(hf) > won:
            raise ValidationError(
                _("%(label)s has %(n)s high finish(es) but won only %(won)s leg(s)."),
                params={"label": label, "n": len(hf), "won": won},
            )
        if ld and len(ld) > won:
            raise ValidationError(
                _("%(label)s has %(n)s low-darts leg(s) but won only %(won)s leg(s)."),
                params={"label": label, "n": len(ld), "won": won},
            )
        if n180 and n180 > MAX_180S_PER_LEG * legs_played:
            raise ValidationError(
                _("%(label)s has %(n)s 180s in %(legs)s leg(s) - at most %(max)s per leg."),
                params={"label": label, "n": n180, "legs": legs_played, "max": MAX_180S_PER_LEG},
            )


def validate_average(value) -> None:
    if value is not None and not (0 < value <= 180):
        raise ValidationError(_("The average must be between 0 and 180."), code="average")
