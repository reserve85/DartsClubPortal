"""Head-to-head comparison of two players over their direct meetings."""

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext as _

from app.elo.models import EloProfile, Match
from app.elo.services.elo import calculate_expected_score
from app.elo.services.ranking import current_positions, validate_range

RECENT_MATCHES = 10


def _empty() -> dict:
    return {
        "wins": 0,
        "legs": 0,
        "elo_net": 0.0,
        "total_180s": 0,
        "high_finishes": [],
        "low_darts": [],
        "averages": [],
    }


def head_to_head(player_a_id: int, player_b_id: int, from_date=None, to_date=None) -> dict:
    if player_a_id == player_b_id:
        raise ValidationError(_("Choose two different players."), code="same_player")
    validate_range(from_date, to_date)
    profiles = {
        p.player_id: p
        for p in EloProfile.objects.select_related("player").filter(
            player_id__in=[player_a_id, player_b_id]
        )
    }
    if len(profiles) != 2:
        raise ValidationError(_("Player not found."), code="not_found")
    qs = Match.objects.filter(
        Q(player_a_id=player_a_id, player_b_id=player_b_id)
        | Q(player_a_id=player_b_id, player_b_id=player_a_id)
    )
    if from_date is not None:
        qs = qs.filter(date__gte=from_date)
    if to_date is not None:
        qs = qs.filter(date__lte=to_date)
    matches = list(qs.order_by("date", "created_at", "id"))

    stats = {player_a_id: _empty(), player_b_id: _empty()}
    for m in matches:
        for pid in (player_a_id, player_b_id):
            s, side = stats[pid], m.side_of(pid)
            s["wins"] += 1 if m.winner_id == pid else 0
            s["legs"] += getattr(m, f"score_{side}") or 0
            s["elo_net"] += getattr(m, f"elo_change_{side}")
            s["total_180s"] += getattr(m, f"{side}_180s") or 0
            s["high_finishes"].extend(getattr(m, f"{side}_high_finishes") or [])
            s["low_darts"].extend(getattr(m, f"{side}_low_darts") or [])
            avg = getattr(m, f"{side}_average")
            if avg is not None:
                s["averages"].append(avg)

    positions = current_positions()

    def summary(pid):
        s, p = stats[pid], profiles[pid]
        return {
            "player_id": pid,
            "name": p.player.name,
            "current_elo": p.current_elo,
            "current_rank": positions.get(pid),
            "disabled": p.disabled,
            "wins": s["wins"],
            "legs_won": s["legs"],
            "elo_net": round(s["elo_net"], 2),
            "total_180s": s["total_180s"],
            "best_high_finish": max(s["high_finishes"]) if s["high_finishes"] else None,
            "best_low_darts": min(s["low_darts"]) if s["low_darts"] else None,
            "high_finishes": sorted(s["high_finishes"], reverse=True),
            "low_darts": sorted(s["low_darts"]),
            "average": round(sum(s["averages"]) / len(s["averages"]), 2) if s["averages"] else None,
        }

    streak = {"player_id": None, "count": 0}
    for m in reversed(matches):
        if streak["player_id"] is None:
            streak = {"player_id": m.winner_id, "count": 1}
        elif m.winner_id == streak["player_id"]:
            streak["count"] += 1
        else:
            break

    recent = []
    for m in reversed(matches[-RECENT_MATCHES:]):
        side = m.side_of(player_a_id)
        other = "b" if side == "a" else "a"
        recent.append(
            {
                "match": m,
                "date": m.date,
                "winner_id": m.winner_id,
                "score_a": getattr(m, f"score_{side}"),
                "score_b": getattr(m, f"score_{other}"),
                "elo_change_a": getattr(m, f"elo_change_{side}"),
                "average_a": getattr(m, f"{side}_average"),
                "average_b": getattr(m, f"{other}_average"),
            }
        )

    timeline, balance = [], 0.0
    for m in matches:
        change = m.elo_change(player_a_id)
        balance += change
        timeline.append(
            {
                "match_id": m.id,
                "date": m.date.isoformat(),
                "winner_id": m.winner_id,
                "elo_change_a": round(change, 2),
                "elo_balance_a": round(balance, 2),
            }
        )

    expected_a = calculate_expected_score(
        profiles[player_a_id].current_elo, profiles[player_b_id].current_elo
    )
    return {
        "total_matches": len(matches),
        "a": summary(player_a_id),
        "b": summary(player_b_id),
        "win_probability_a": round(expected_a, 4),
        "win_probability_b": round(1.0 - expected_a, 4),
        "streak": streak,
        "first_meeting": matches[0].date if matches else None,
        "last_meeting": matches[-1].date if matches else None,
        "recent": recent,
        "timeline": timeline,
    }


def opponents(player_id: int) -> list[dict]:
    """Every player ``player_id`` has met at least once, most-played first."""
    agg: dict[int, dict] = {}
    for m in Match.objects.filter(Q(player_a_id=player_id) | Q(player_b_id=player_id)):
        opp = m.opponent_id(player_id)
        rec = agg.setdefault(opp, {"matches": 0, "wins": 0, "losses": 0, "last": m.date})
        rec["matches"] += 1
        rec["wins" if m.winner_id == player_id else "losses"] += 1
        rec["last"] = max(rec["last"], m.date)
    names = {
        p.player_id: (p.player.name, p.disabled)
        for p in EloProfile.objects.select_related("player").filter(player_id__in=list(agg))
    }
    out = [
        {
            "player_id": pid,
            "name": names.get(pid, ("?", False))[0],
            "disabled": names.get(pid, ("?", False))[1],
            **rec,
        }
        for pid, rec in agg.items()
    ]
    out.sort(key=lambda r: (-r["matches"], r["name"]))
    return out
