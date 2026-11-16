"""Elo module models.

``players.Player`` is the shared person of the portal. The Elo module adds an
:class:`EloProfile` (1:1) holding the Elo-specific state, so a person can be
part of the Elo ranking, the penalty module, or both.

Matches are ordered deterministically by ``(date, created_at, id)`` - the
timeline order every Elo recalculation replays.
"""

from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class EloProfile(models.Model):
    """Elo state of a player (start Elo, current Elo, member-since date)."""

    player = models.OneToOneField(
        "players.Player",
        on_delete=models.CASCADE,
        related_name="elo",
        verbose_name=_("player"),
    )
    start_elo = models.IntegerField(_("start Elo"))
    current_elo = models.FloatField(_("current Elo"))
    # Member-since date: a player is part of the ranking field from this day on.
    entry_date = models.DateField(_("entry date"))
    # True once the player has played (reset when every match is deleted).
    active = models.BooleanField(_("has played"), default=False)
    # Disabled players stay in the ranking field but cannot play new matches.
    disabled = models.BooleanField(_("disabled"), default=False)
    last_match_date = models.DateField(_("last match"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        ordering: ClassVar[list] = ["player__name"]
        verbose_name = _("Elo profile")
        verbose_name_plural = _("Elo profiles")

    def __str__(self):
        return f"{self.player.name} ({self.current_elo:.0f})"

    @property
    def name(self) -> str:
        return self.player.name


class EloDisablePeriod(models.Model):
    """Audit trail: every interval a player was disabled (open end = still disabled)."""

    profile = models.ForeignKey(
        EloProfile, on_delete=models.CASCADE, related_name="disable_periods"
    )
    disabled_from = models.DateField()
    disabled_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar[list] = ["disabled_from"]


class EloMonthlyReport(models.Model):
    """Marks a month whose summary mails went out (never twice)."""

    month = models.DateField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.month.strftime("%Y-%m")


class Match(models.Model):
    """One singles match with its result, Elo snapshots and dart statistics."""

    date = models.DateField(_("date"), db_index=True)
    player_a = models.ForeignKey(
        "players.Player",
        on_delete=models.PROTECT,
        related_name="elo_matches_as_a",
        verbose_name=_("player A"),
    )
    player_b = models.ForeignKey(
        "players.Player",
        on_delete=models.PROTECT,
        related_name="elo_matches_as_b",
        verbose_name=_("player B"),
    )
    best_of_legs = models.PositiveSmallIntegerField(_("best of legs"), default=5)
    # Legs won (NULL only for legacy matches imported without a leg score).
    score_a = models.PositiveSmallIntegerField(_("legs A"), null=True, blank=True)
    score_b = models.PositiveSmallIntegerField(_("legs B"), null=True, blank=True)
    winner = models.ForeignKey(
        "players.Player", on_delete=models.PROTECT, related_name="+", verbose_name=_("winner")
    )
    loser = models.ForeignKey(
        "players.Player", on_delete=models.PROTECT, related_name="+", verbose_name=_("loser")
    )
    elo_before_a = models.FloatField(default=0.0)
    elo_before_b = models.FloatField(default=0.0)
    elo_after_a = models.FloatField(default=0.0)
    elo_after_b = models.FloatField(default=0.0)
    elo_change_a = models.FloatField(default=0.0)
    elo_change_b = models.FloatField(default=0.0)
    # K-factor snapshot from the configuration at creation time.
    k_factor = models.FloatField(default=32.0)
    a_180s = models.PositiveSmallIntegerField(default=0)
    b_180s = models.PositiveSmallIntegerField(default=0)
    a_high_finishes = models.JSONField(default=list, blank=True)
    b_high_finishes = models.JSONField(default=list, blank=True)
    a_low_darts = models.JSONField(default=list, blank=True)
    b_low_darts = models.JSONField(default=list, blank=True)
    a_average = models.FloatField(null=True, blank=True)
    b_average = models.FloatField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("entered by"),
    )
    created_at = models.DateTimeField(_("created at"), db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    TIMELINE_ORDER: ClassVar[tuple] = ("date", "created_at", "id")

    class Meta:
        ordering: ClassVar[list] = ["date", "created_at", "id"]
        verbose_name = _("match")
        verbose_name_plural = _("matches")
        indexes: ClassVar[list] = [
            models.Index(fields=["date", "created_at", "id"], name="elo_match_timeline"),
        ]
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=~Q(player_a=models.F("player_b")), name="elo_match_two_players"
            ),
        ]

    def __str__(self):
        return f"{self.date} {self.player_a} {self.score_a}:{self.score_b} {self.player_b}"

    def save(self, *args, **kwargs):
        if self.created_at is None:
            from django.utils import timezone

            self.created_at = timezone.now()
        super().save(*args, **kwargs)

    def timeline_key(self) -> tuple:
        return (self.date, self.created_at, self.id)

    def side_of(self, player_id: int) -> str:
        """'a' when ``player_id`` is player A of this match, else 'b'."""
        return "a" if self.player_a_id == player_id else "b"

    def stat(self, player_id: int, field: str):
        """Per-player value, e.g. ``stat(pid, "180s")`` or ``stat(pid, "average")``."""
        return getattr(self, f"{self.side_of(player_id)}_{field}")

    def elo_after(self, player_id: int) -> float:
        return self.elo_after_a if self.player_a_id == player_id else self.elo_after_b

    def elo_change(self, player_id: int) -> float:
        return self.elo_change_a if self.player_a_id == player_id else self.elo_change_b

    def legs(self, player_id: int):
        return self.score_a if self.player_a_id == player_id else self.score_b

    def opponent_id(self, player_id: int) -> int:
        return self.player_b_id if self.player_a_id == player_id else self.player_a_id
