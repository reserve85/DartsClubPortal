"""Match entry, editing, deletion and the historical Elo recalculation.

Whenever a match is added, edited or deleted, the affected part of the
timeline is replayed in the deterministic order ``(date, created_at, id)``.

Boundary rule (ported from EloRankingSystem, "Fix #12"):
- players of the changed match enter the window at their ``start_elo``; the
  window starts at the earliest match of any of them, so their whole history
  is replayed,
- every other player met inside the window enters at the Elo after their last
  match strictly before the window (or ``start_elo`` without one).
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from app.core.models import AuditAction
from app.core.services import log_action
from app.elo.conf import elo_setting
from app.elo.models import EloProfile, Match
from app.elo.services.elo import calculate_match_elo
from app.elo.services.validation import (
    determine_winner,
    validate_average,
    validate_best_of,
    validate_statistics,
    validate_statistics_against_score,
)

STAT_FIELDS = (
    "a_180s",
    "b_180s",
    "a_high_finishes",
    "b_high_finishes",
    "a_low_darts",
    "b_low_darts",
    "a_average",
    "b_average",
)


class DuplicateMatchError(ValidationError):
    """Same players, same result, same day - confirm to save anyway."""


def match_snapshot(match: Match) -> dict:
    return {
        "date": match.date.isoformat(),
        "player_a": match.player_a_id,
        "player_b": match.player_b_id,
        "score": f"{match.score_a}:{match.score_b}",
        "best_of": match.best_of_legs,
        "winner": match.winner_id,
        "statistics": {f: getattr(match, f) for f in STAT_FIELDS},
    }


def _player_matches(player_id: int):
    return Match.objects.filter(Q(player_a_id=player_id) | Q(player_b_id=player_id))


def _at_or_after(m: Match) -> Q:
    return (
        Q(date__gt=m.date)
        | Q(date=m.date, created_at__gt=m.created_at)
        | Q(date=m.date, created_at=m.created_at, id__gte=m.id)
    )


def _before(m: Match) -> Q:
    return (
        Q(date__lt=m.date)
        | Q(date=m.date, created_at__lt=m.created_at)
        | Q(date=m.date, created_at=m.created_at, id__lt=m.id)
    )


def find_duplicate(player_a_id, player_b_id, score_a, score_b, match_date, exclude_id=None):
    """A match between the same two players, same day, same result (either side)."""
    qs = Match.objects.filter(date=match_date).filter(
        Q(player_a_id=player_a_id, player_b_id=player_b_id, score_a=score_a, score_b=score_b)
        | Q(player_a_id=player_b_id, player_b_id=player_a_id, score_a=score_b, score_b=score_a)
    )
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    return qs.first()


def _profile(player) -> EloProfile:
    try:
        return player.elo
    except EloProfile.DoesNotExist as exc:
        raise ValidationError(
            _("%(name)s is not part of the Elo ranking."), params={"name": player.name}
        ) from exc


def _validate_date(match_date, profiles) -> None:
    if match_date > timezone.localdate():
        raise ValidationError(_("The match date lies in the future."), code="future")
    for profile in profiles:
        if match_date < profile.entry_date:
            raise ValidationError(
                _(
                    "The match date is before the entry date %(entry)s of %(name)s. "
                    "Adjust the player's entry date first."
                ),
                params={"entry": profile.entry_date.strftime("%d.%m.%Y"), "name": profile.name},
                code="entry_date",
            )


def _clean_stats(stats: dict) -> dict:
    out = {}
    for f in STAT_FIELDS:
        if f not in stats:
            continue
        value = stats[f]
        if f.endswith(("high_finishes", "low_darts")):
            value = [int(v) for v in (value or [])]
        elif f.endswith("180s"):
            value = int(value or 0)
            if value < 0:
                raise ValidationError(_("180s cannot be negative."))
        elif value is not None and value != "":
            value = round(float(value), 2)
        else:
            value = None
        out[f] = value
    return out


@transaction.atomic
def create_match(
    *,
    player_a,
    player_b,
    match_date,
    score_a: int,
    score_b: int,
    best_of_legs: int | None = None,
    stats: dict | None = None,
    user=None,
    force: bool = False,
) -> Match:
    """Validate, store and replay the timeline. Raises ValidationError."""
    if player_a.pk == player_b.pk:
        raise ValidationError(_("Choose two different players."), code="same_player")
    pa, pb = _profile(player_a), _profile(player_b)
    for profile in (pa, pb):
        if profile.disabled:
            raise ValidationError(
                _("%(name)s is disabled and cannot play matches."),
                params={"name": profile.name},
                code="disabled",
            )
    _validate_date(match_date, (pa, pb))
    bol = validate_best_of(best_of_legs or elo_setting("BEST_OF_LEGS"))
    winner = determine_winner(score_a, score_b, bol)
    stats = _clean_stats(stats or {})
    validate_statistics(
        stats.get("a_high_finishes"),
        stats.get("b_high_finishes"),
        stats.get("a_low_darts"),
        stats.get("b_low_darts"),
    )
    validate_statistics_against_score(
        score_a,
        score_b,
        stats.get("a_180s"),
        stats.get("b_180s"),
        stats.get("a_high_finishes"),
        stats.get("b_high_finishes"),
        stats.get("a_low_darts"),
        stats.get("b_low_darts"),
    )
    validate_average(stats.get("a_average"))
    validate_average(stats.get("b_average"))
    if not force:
        dup = find_duplicate(player_a.pk, player_b.pk, score_a, score_b, match_date)
        if dup is not None:
            raise DuplicateMatchError(
                _("A match with the same result on the same day already exists."),
                code="duplicate",
            )
    match = Match(
        date=match_date,
        player_a=player_a,
        player_b=player_b,
        best_of_legs=bol,
        score_a=score_a,
        score_b=score_b,
        winner=player_a if winner == "A" else player_b,
        loser=player_b if winner == "A" else player_a,
        k_factor=float(elo_setting("K_FACTOR")),
        created_by=user if user is not None and user.is_authenticated else None,
        **stats,
    )
    match.save()
    recalculate_timeline({player_a.pk, player_b.pk})
    match.refresh_from_db()
    log_action(
        AuditAction.ELO_MATCH_CREATED,
        user=_actor(user),
        target=match,
        metadata=match_snapshot(match),
    )
    return match


@transaction.atomic
def update_match(match: Match, *, user=None, force: bool = False, **changes) -> Match:
    """Change date / score / format / statistics, then replay the timeline.

    Every value is validated against the *effective* match (stored values
    overlaid with the changes) before anything is written.
    """
    old = match_snapshot(match)
    pa, pb = _profile(match.player_a), _profile(match.player_b)
    eff_date = changes.get("match_date") or match.date
    eff_bol = changes.get("best_of_legs") or match.best_of_legs
    eff_a = changes.get("score_a", match.score_a)
    eff_b = changes.get("score_b", match.score_b)
    validate_best_of(eff_bol)
    winner = None
    if eff_a is not None and eff_b is not None:
        winner = determine_winner(eff_a, eff_b, eff_bol)
    if "match_date" in changes:
        _validate_date(eff_date, (pa, pb))
    stats = _clean_stats({f: changes[f] for f in STAT_FIELDS if f in changes})

    def eff(f):
        return stats[f] if f in stats else getattr(match, f)

    validate_statistics(
        eff("a_high_finishes"), eff("b_high_finishes"), eff("a_low_darts"), eff("b_low_darts")
    )
    if eff_a is not None and eff_b is not None:
        validate_statistics_against_score(
            eff_a,
            eff_b,
            eff("a_180s"),
            eff("b_180s"),
            eff("a_high_finishes"),
            eff("b_high_finishes"),
            eff("a_low_darts"),
            eff("b_low_darts"),
        )
    validate_average(eff("a_average"))
    validate_average(eff("b_average"))
    if not force and (eff_date != match.date or (eff_a, eff_b) != (match.score_a, match.score_b)):
        dup = find_duplicate(
            match.player_a_id, match.player_b_id, eff_a, eff_b, eff_date, exclude_id=match.pk
        )
        if dup is not None:
            raise DuplicateMatchError(
                _("A match with the same result on the same day already exists."),
                code="duplicate",
            )
    match.date = eff_date
    match.best_of_legs = eff_bol
    match.score_a, match.score_b = eff_a, eff_b
    if winner is not None:
        match.winner_id = match.player_a_id if winner == "A" else match.player_b_id
        match.loser_id = match.player_b_id if winner == "A" else match.player_a_id
    for f, value in stats.items():
        setattr(match, f, value)
    match.save()
    recalculate_timeline({match.player_a_id, match.player_b_id})
    match.refresh_from_db()
    log_action(
        AuditAction.ELO_MATCH_UPDATED,
        user=_actor(user),
        target=match,
        metadata={"old": old, "new": match_snapshot(match)},
    )
    return match


@transaction.atomic
def delete_match(match: Match, *, user=None) -> None:
    affected = {match.player_a_id, match.player_b_id}
    snapshot = match_snapshot(match)
    match_id = match.pk
    match.delete()
    recalculate_timeline(affected)
    log_action(
        AuditAction.ELO_MATCH_DELETED,
        user=_actor(user),
        metadata={"match_id": match_id, "old": snapshot},
    )


def _actor(user):
    return user if user is not None and getattr(user, "is_authenticated", False) else None


def recalculate_timeline(affected_player_ids: set[int]) -> int:
    """Replay the Elo timeline from the earliest match of the affected players.

    Returns the number of replayed matches.
    """
    if not affected_player_ids:
        return 0
    first = (
        Match.objects.filter(
            Q(player_a_id__in=affected_player_ids) | Q(player_b_id__in=affected_player_ids)
        )
        .order_by("date", "created_at", "id")
        .first()
    )
    profiles_all = {p.player_id: p for p in EloProfile.objects.select_related("player")}
    if first is None:
        _reset(profiles_all, affected_player_ids)
        return 0

    window = list(Match.objects.filter(_at_or_after(first)).order_by("date", "created_at", "id"))
    in_window = {m.player_a_id for m in window} | {m.player_b_id for m in window}

    state: dict[int, list] = {}  # pid -> [elo, last_match_date]
    for pid in in_window:
        profile = profiles_all.get(pid)
        if profile is None:
            continue
        if pid in affected_player_ids:
            state[pid] = [float(profile.start_elo), None]
            continue
        prev = (
            _player_matches(pid)
            .filter(_before(first))
            .order_by("-date", "-created_at", "-id")
            .first()
        )
        if prev is not None:
            state[pid] = [prev.elo_after(pid), prev.date]
        else:
            state[pid] = [float(profile.start_elo), None]

    for m in window:
        sa, sb = state.get(m.player_a_id), state.get(m.player_b_id)
        if sa is None or sb is None:
            continue
        res = calculate_match_elo(
            sa[0], sb[0], "A" if m.winner_id == m.player_a_id else "B", k_factor=m.k_factor
        )
        m.elo_before_a, m.elo_before_b = sa[0], sb[0]
        m.elo_after_a, m.elo_after_b = res.new_rating_a, res.new_rating_b
        m.elo_change_a, m.elo_change_b = res.change_a, res.change_b
        sa[0], sb[0] = res.new_rating_a, res.new_rating_b
        sa[1] = sb[1] = m.date

    Match.objects.bulk_update(
        window,
        [
            "elo_before_a",
            "elo_before_b",
            "elo_after_a",
            "elo_after_b",
            "elo_change_a",
            "elo_change_b",
        ],
        batch_size=500,
    )
    changed = []
    for pid, (elo, last) in state.items():
        profile = profiles_all[pid]
        profile.current_elo = elo
        profile.last_match_date = last
        profile.active = last is not None
        changed.append(profile)
    if changed:
        EloProfile.objects.bulk_update(changed, ["current_elo", "last_match_date", "active"])
    _reset(profiles_all, affected_player_ids - set(state))
    return len(window)


def _reset(profiles: dict, player_ids) -> None:
    """Players without any remaining match go back to their initial state."""
    reset = []
    for pid in player_ids:
        profile = profiles.get(pid)
        if profile is None:
            continue
        if _player_matches(pid).exists():
            continue
        profile.current_elo = float(profile.start_elo)
        profile.last_match_date = None
        profile.active = False
        reset.append(profile)
    if reset:
        EloProfile.objects.bulk_update(reset, ["current_elo", "last_match_date", "active"])


@transaction.atomic
def recalculate_all(*, user=None) -> dict:
    """Replay the complete history from scratch (data repair)."""
    ids = set(EloProfile.objects.values_list("player_id", flat=True))
    count = recalculate_timeline(ids)
    log_action(
        AuditAction.ELO_RECALCULATED,
        user=_actor(user),
        metadata={"matches": count, "players": len(ids)},
    )
    return {"matches_recalculated": count, "players_affected": len(ids)}
