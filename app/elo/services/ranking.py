"""Ranking, player statistics, histories and all-time highs.

Positions are always computed over the FULL field - every player whose entry
date is on or before the period end, inactive and disabled players included.
The "include inactive" switch only decides which rows are shown, never the
position numbers, so a position is identical with and without the switch and
consistent with Best Rank.
"""

import calendar
from dataclasses import dataclass, field
from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from app.elo.conf import elo_setting
from app.elo.models import EloProfile, Match


def validate_range(from_date, to_date) -> None:
    if from_date is not None and to_date is not None and from_date > to_date:
        raise ValidationError(_("The start date cannot be after the end date."), code="range")


def inactive_cutoff(as_of: date) -> date:
    months = elo_setting("INACTIVITY_MONTHS")
    year, month = as_of.year, as_of.month - months
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, min(as_of.day, calendar.monthrange(year, month)[1]))


def is_inactive(last_match, as_of: date) -> bool:
    """Inactive = no match by ``as_of`` or the last one older than the cutoff."""
    if last_match is None or last_match > as_of:
        return True
    return last_match < inactive_cutoff(as_of)


@dataclass
class RankingEntry:
    player_id: int
    name: str
    disabled: bool
    inactive: bool
    position: int
    elo: float
    elo_change: float
    position_change: int | None
    matches: int
    wins: int
    total_180s: int
    high_finishes: list = field(default_factory=list)
    low_darts: list = field(default_factory=list)

    @property
    def best_high_finish(self):
        return self.high_finishes[0] if self.high_finishes else None

    @property
    def best_low_darts(self):
        return self.low_darts[0] if self.low_darts else None


@dataclass
class Ranking:
    from_date: date
    to_date: date
    entries: list
    field_size: int


def default_period(today: date | None = None) -> tuple[date, date]:
    today = today or timezone.localdate()
    return date(today.year, today.month, 1), today


def field_profiles(as_of: date):
    return list(EloProfile.objects.select_related("player").filter(entry_date__lte=as_of))


def _records(from_date: date, to_date: date) -> dict[int, dict]:
    """One query up to ``to_date``, aggregated per player in timeline order."""
    records: dict[int, dict] = {}
    rows = (
        Match.objects.filter(date__lte=to_date)
        .order_by("date", "created_at", "id")
        .values_list(
            "date",
            "player_a_id",
            "player_b_id",
            "winner_id",
            "elo_after_a",
            "elo_after_b",
            "a_180s",
            "b_180s",
            "a_high_finishes",
            "b_high_finishes",
            "a_low_darts",
            "b_low_darts",
        )
    )
    for d, pa, pb, win, ea, eb, a180, b180, ahf, bhf, ald, bld in rows:
        for pid, elo_after, n180, hf, ld in ((pa, ea, a180, ahf, ald), (pb, eb, b180, bhf, bld)):
            rec = records.setdefault(
                pid,
                {
                    "elo_at_start": None,
                    "elo_at_end": None,
                    "last": None,
                    "matches": 0,
                    "wins": 0,
                    "180s": 0,
                    "hf": [],
                    "ld": [],
                },
            )
            rec["elo_at_end"] = elo_after
            rec["last"] = d
            if d < from_date:
                rec["elo_at_start"] = elo_after
                continue
            rec["matches"] += 1
            rec["wins"] += 1 if win == pid else 0
            rec["180s"] += n180 or 0
            rec["hf"].extend(hf or [])
            rec["ld"].extend(ld or [])
    return records


def generate_ranking(from_date=None, to_date=None, include_inactive: bool = False) -> Ranking:
    if to_date is None:
        to_date = timezone.localdate()
    if from_date is None:
        from_date = date(to_date.year, to_date.month, 1)
    validate_range(from_date, to_date)
    profiles = field_profiles(to_date)
    records = _records(from_date, to_date)
    rows = []
    for p in profiles:
        rec = records.get(p.player_id)
        if rec is None:
            start = end = float(p.start_elo)
            rows.append(
                {
                    "p": p,
                    "start": start,
                    "end": end,
                    "matches": 0,
                    "wins": 0,
                    "180s": 0,
                    "hf": [],
                    "ld": [],
                    "inactive": True,
                    "has_history": False,
                }
            )
            continue
        start = rec["elo_at_start"] if rec["elo_at_start"] is not None else float(p.start_elo)
        rows.append(
            {
                "p": p,
                "start": start,
                "end": rec["elo_at_end"],
                "matches": rec["matches"],
                "wins": rec["wins"],
                "180s": rec["180s"],
                "hf": sorted(rec["hf"], reverse=True),
                "ld": sorted(rec["ld"]),
                "inactive": is_inactive(rec["last"], to_date),
                "has_history": True,
            }
        )
    rows.sort(key=lambda r: (-r["end"], r["p"].player.name))
    start_pos = {
        r["p"].player_id: i + 1
        for i, r in enumerate(sorted(rows, key=lambda r: (-r["start"], r["p"].player.name)))
    }
    entries = []
    for i, r in enumerate(rows):
        pos = i + 1
        p = r["p"]
        if not include_inactive and (p.disabled or (r["inactive"] and r["matches"] == 0)):
            continue
        change = start_pos[p.player_id] - pos if r["has_history"] else None
        entries.append(
            RankingEntry(
                player_id=p.player_id,
                name=p.player.name,
                disabled=p.disabled,
                inactive=r["inactive"],
                position=pos,
                elo=r["end"],
                elo_change=r["end"] - r["start"],
                position_change=change,
                matches=r["matches"],
                wins=r["wins"],
                total_180s=r["180s"],
                high_finishes=r["hf"],
                low_darts=r["ld"],
            )
        )
    return Ranking(from_date, to_date, entries, len(rows))


def current_positions() -> dict[int, int]:
    """Today's full-field position of every player (same numbers as the table)."""
    return {e.player_id: e.position for e in generate_ranking(include_inactive=True).entries}


def player_matches(player_id: int):
    return (
        Match.objects.filter(Q(player_a_id=player_id) | Q(player_b_id=player_id))
        .select_related("player_a", "player_b")
        .order_by("date", "created_at", "id")
    )


def _aggregate(matches, pid: int) -> dict:
    out = {
        "matches": len(matches),
        "wins": 0,
        "losses": 0,
        "legs_won": 0,
        "legs_lost": 0,
        "total_180s": 0,
        "high_finishes": [],
        "low_darts": [],
        "average": None,
        "average_count": 0,
    }
    averages = []
    for m in matches:
        side = m.side_of(pid)
        other = "b" if side == "a" else "a"
        out["total_180s"] += getattr(m, f"{side}_180s") or 0
        out["high_finishes"].extend(getattr(m, f"{side}_high_finishes") or [])
        out["low_darts"].extend(getattr(m, f"{side}_low_darts") or [])
        avg = getattr(m, f"{side}_average")
        if avg is not None:
            averages.append(avg)
        out["legs_won"] += getattr(m, f"score_{side}") or 0
        out["legs_lost"] += getattr(m, f"score_{other}") or 0
        if m.winner_id == pid:
            out["wins"] += 1
        else:
            out["losses"] += 1
    out["high_finishes"].sort(reverse=True)
    out["low_darts"].sort()
    if averages:
        out["average"] = round(sum(averages) / len(averages), 2)
        out["average_count"] = len(averages)
    out["win_rate"] = round(100 * out["wins"] / out["matches"]) if out["matches"] else None
    return out


def player_statistics(player_id: int, from_date=None, to_date=None) -> dict:
    validate_range(from_date, to_date)
    matches = list(player_matches(player_id))
    period = [
        m
        for m in matches
        if (from_date is None or m.date >= from_date) and (to_date is None or m.date <= to_date)
    ]
    all_time = _aggregate(matches, player_id)
    last_avgs = [
        a for a in (m.stat(player_id, "average") for m in reversed(matches)) if a is not None
    ][:100]
    all_time["average_last100"] = round(sum(last_avgs) / len(last_avgs), 2) if last_avgs else None
    return {"period": _aggregate(period, player_id), "all_time": all_time}


def elo_history(player_id: int) -> list[dict]:
    return [
        {"date": m.date.isoformat(), "elo": round(m.elo_after(player_id), 1), "match_id": m.id}
        for m in player_matches(player_id)
    ]


def average_history(player_id: int) -> list[dict]:
    out = []
    for m in player_matches(player_id):
        avg = m.stat(player_id, "average")
        if avg is not None:
            out.append({"date": m.date.isoformat(), "average": avg, "match_id": m.id})
    return out


def all_time_high_elo(profile: EloProfile) -> dict:
    best, when = float(profile.start_elo), None
    for m in player_matches(profile.player_id):
        elo = m.elo_after(profile.player_id)
        if elo > best:
            best, when = elo, m.date
    return {"max_elo": best, "date_reached": when}


def all_players_all_time_high(include_inactive: bool = False) -> list[dict]:
    profiles = {p.player_id: p for p in EloProfile.objects.select_related("player")}
    ath = {pid: [float(p.start_elo), None] for pid, p in profiles.items()}
    for d, pa, pb, ea, eb in Match.objects.order_by("date", "created_at", "id").values_list(
        "date", "player_a_id", "player_b_id", "elo_after_a", "elo_after_b"
    ):
        for pid, elo in ((pa, ea), (pb, eb)):
            rec = ath.get(pid)
            if rec is not None and elo > rec[0]:
                rec[0], rec[1] = elo, d
    today = timezone.localdate()
    out = []
    for pid, p in profiles.items():
        inactive = is_inactive(p.last_match_date, today)
        if not include_inactive and (p.disabled or inactive):
            continue
        out.append(
            {
                "player_id": pid,
                "name": p.player.name,
                "max_elo": ath[pid][0],
                "date_reached": ath[pid][1],
                "inactive": inactive,
                "disabled": p.disabled,
            }
        )
    out.sort(key=lambda x: (-x["max_elo"], x["name"]))
    return out


def best_rank(player_id: int) -> dict:
    """Lowest rank number ever reached, evaluated at the end of each match day.

    The field of a day is every player entered by that day (disabled ones
    included); ties are broken by name exactly like the ranking table.
    """
    profiles = list(EloProfile.objects.select_related("player"))
    if not any(p.player_id == player_id for p in profiles):
        return {"best_rank": None, "date_reached": None}
    rows = list(
        Match.objects.order_by("date", "created_at", "id").values_list(
            "date", "player_a_id", "player_b_id", "elo_after_a", "elo_after_b"
        )
    )
    target_days = {d for d, pa, pb, _a, _b in rows if player_id in (pa, pb)}
    if not target_days:
        return {"best_rank": None, "date_reached": None}
    elos = {p.player_id: float(p.start_elo) for p in profiles}
    names = {p.player_id: p.player.name for p in profiles}
    by_entry = sorted(profiles, key=lambda p: p.entry_date)
    nxt, eligible = 0, set()
    best, best_day = None, None
    i = 0
    while i < len(rows):
        day = rows[i][0]
        while i < len(rows) and rows[i][0] == day:
            _d, pa, pb, ea, eb = rows[i]
            if pa in elos:
                elos[pa] = ea
            if pb in elos:
                elos[pb] = eb
            i += 1
        while nxt < len(by_entry) and by_entry[nxt].entry_date <= day:
            eligible.add(by_entry[nxt].player_id)
            nxt += 1
        if day not in target_days or player_id not in eligible:
            continue
        key = (-elos[player_id], names[player_id])
        rank = 1 + sum(1 for pid in eligible if pid != player_id and (-elos[pid], names[pid]) < key)
        if best is None or rank < best:
            best, best_day = rank, day
    return {"best_rank": best, "date_reached": best_day}
