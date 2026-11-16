"""Elo player management: join the ranking, edit, disable, reactivate."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Min, Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext as _

from app.core.models import AuditAction
from app.core.services import log_action
from app.elo.conf import elo_setting
from app.elo.models import EloDisablePeriod, EloProfile, Match
from app.players.models import Player


def _actor(user):
    return user if user is not None and getattr(user, "is_authenticated", False) else None


def _check_name_free(name: str, exclude_player_id=None) -> None:
    qs = EloProfile.objects.annotate(n=Lower("player__name")).filter(n=name.strip().lower())
    if exclude_player_id is not None:
        qs = qs.exclude(player_id=exclude_player_id)
    if qs.exists():
        raise ValidationError(
            _("A player named %(name)s is already in the Elo ranking."),
            params={"name": name},
            code="duplicate_name",
        )


def _check_entry_date(entry_date) -> None:
    if entry_date > timezone.localdate():
        raise ValidationError(_("The entry date cannot lie in the future."), code="entry_future")


@transaction.atomic
def add_to_ranking(
    *, player: Player | None = None, name: str = "", start_elo=None, entry_date=None, user=None
) -> EloProfile:
    """Put an existing person (``player``) or a new one (``name``) into the ranking."""
    if player is None:
        name = (name or "").strip()
        if not name:
            raise ValidationError(_("Please enter a name."), code="name")
        _check_name_free(name)
        player = Player.objects.create(name=name)
    else:
        if EloProfile.objects.filter(player=player).exists():
            raise ValidationError(_("This player is already in the Elo ranking."), code="exists")
        _check_name_free(player.name)
    entry_date = entry_date or timezone.localdate()
    _check_entry_date(entry_date)
    start = int(start_elo if start_elo not in (None, "") else elo_setting("DEFAULT_ELO"))
    profile = EloProfile.objects.create(
        player=player, start_elo=start, current_elo=float(start), entry_date=entry_date
    )
    log_action(
        AuditAction.ELO_PLAYER_CREATED,
        user=_actor(user),
        target=player,
        metadata={"start_elo": start, "entry_date": entry_date.isoformat()},
    )
    return profile


def first_match_date(player_id: int):
    return Match.objects.filter(Q(player_a_id=player_id) | Q(player_b_id=player_id)).aggregate(
        d=Min("date")
    )["d"]


@transaction.atomic
def update_profile(
    profile: EloProfile, *, name=None, start_elo=None, entry_date=None, user=None
) -> EloProfile:
    """Rename / change start Elo (replays the timeline) / change the entry date."""
    from app.elo.services.matches import recalculate_timeline

    old = {
        "name": profile.player.name,
        "start_elo": profile.start_elo,
        "entry_date": profile.entry_date.isoformat(),
    }
    if name is not None and name.strip() and name.strip() != profile.player.name:
        _check_name_free(name, exclude_player_id=profile.player_id)
        profile.player.name = name.strip()
        profile.player.save(update_fields=["name"])
    if entry_date is not None and entry_date != profile.entry_date:
        _check_entry_date(entry_date)
        first = first_match_date(profile.player_id)
        if first is not None and entry_date > first:
            raise ValidationError(
                _("The entry date cannot be after the first match on %(date)s."),
                params={"date": first.strftime("%d.%m.%Y")},
                code="entry_after_first_match",
            )
        profile.entry_date = entry_date
    replay = False
    if start_elo not in (None, "") and int(start_elo) != profile.start_elo:
        profile.start_elo = int(start_elo)
        replay = True
    profile.save()
    if replay:
        recalculate_timeline({profile.player_id})
        profile.refresh_from_db()
    log_action(
        AuditAction.ELO_PLAYER_UPDATED,
        user=_actor(user),
        target=profile.player,
        metadata={
            "old": old,
            "new": {
                "name": profile.player.name,
                "start_elo": profile.start_elo,
                "entry_date": profile.entry_date.isoformat(),
            },
        },
    )
    return profile


@transaction.atomic
def disable(profile: EloProfile, *, user=None) -> EloProfile:
    """Disabled players stay in the ranking field but cannot play new matches."""
    if not profile.disabled:
        profile.disabled = True
        profile.save(update_fields=["disabled", "updated_at"])
        if not profile.disable_periods.filter(disabled_to__isnull=True).exists():
            EloDisablePeriod.objects.create(profile=profile, disabled_from=timezone.localdate())
        log_action(AuditAction.ELO_PLAYER_DISABLED, user=_actor(user), target=profile.player)
    return profile


@transaction.atomic
def reactivate(profile: EloProfile, *, user=None) -> EloProfile:
    if profile.disabled:
        profile.disabled = False
        profile.save(update_fields=["disabled", "updated_at"])
        profile.disable_periods.filter(disabled_to__isnull=True).update(
            disabled_to=timezone.localdate()
        )
        log_action(AuditAction.ELO_PLAYER_REACTIVATED, user=_actor(user), target=profile.player)
    return profile
