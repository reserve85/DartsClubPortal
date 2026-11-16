"""Elo formula (winner/loser only, no draws).

Expected(A) = 1 / (1 + 10^((RatingB - RatingA) / 400))
NewRating   = OldRating + K * (Actual - Expected)
"""

from dataclasses import dataclass

from app.elo.conf import elo_setting


@dataclass
class EloResult:
    new_rating_a: float
    new_rating_b: float
    expected_a: float
    expected_b: float
    change_a: float
    change_b: float


def calculate_expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def calculate_new_rating(
    current_rating: float, actual_score: float, expected_score: float, k_factor: float | None = None
) -> float:
    if k_factor is None:
        k_factor = float(elo_setting("K_FACTOR"))
    return current_rating + k_factor * (actual_score - expected_score)


def calculate_match_elo(
    rating_a: float, rating_b: float, winner: str, k_factor: float | None = None
) -> EloResult:
    if winner not in ("A", "B"):
        raise ValueError(f"Winner must be 'A' or 'B', got '{winner}'")
    if k_factor is None:
        k_factor = float(elo_setting("K_FACTOR"))
    expected_a = calculate_expected_score(rating_a, rating_b)
    expected_b = 1.0 - expected_a
    actual_a = 1.0 if winner == "A" else 0.0
    actual_b = 1.0 - actual_a
    new_a = calculate_new_rating(rating_a, actual_a, expected_a, k_factor)
    new_b = calculate_new_rating(rating_b, actual_b, expected_b, k_factor)
    return EloResult(new_a, new_b, expected_a, expected_b, new_a - rating_a, new_b - rating_b)
