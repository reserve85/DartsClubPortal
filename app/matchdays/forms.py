"""Matchday form — opponent, team, season, venue, date. NO participants.

Participants are not part of this form anymore: they are assigned
exclusively with the "Add players" editor on the matchday detail page.
"""

from typing import ClassVar

from django import forms
from django.utils.translation import gettext_lazy as _

from app.core.permissions import user_is_captain, user_is_penalty_admin
from app.matchdays.models import Matchday, Season
from app.teams.models import Team
from app.teams.services import teams_for_season


class SeasonForm(forms.ModelForm):
    """Admin: create or edit a season — name, active teams, default flag.

    ``teams`` is optional: an empty selection activates EVERY team (that is
    how seasons behave that were created before per-season teams existed).
    """

    teams = forms.ModelMultipleChoiceField(
        queryset=Team.objects.all(),
        required=False,
        label=_("Active teams"),
        help_text=_(
            "Only these teams are active in this season. Select no team to activate every team."
        ),
    )

    class Meta:
        model = Season
        fields: ClassVar[list] = ["name", "teams", "is_default"]
        widgets: ClassVar[dict] = {"name": forms.TextInput(attrs={"placeholder": "2026/2027"})}
        labels: ClassVar[dict] = {"is_default": _("Default season")}
        help_texts: ClassVar[dict] = {
            "is_default": _(
                "The default season is shown to every user who has not picked "
                "a season themselves. A personal choice in the navbar only "
                "lasts for the session and never changes this default."
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # The chip template compares primary keys, so expose pks (the
            # automatic initial would be a Team queryset).
            self.initial["teams"] = list(self.instance.teams.values_list("pk", flat=True))
        # One nuLiga team page per team: the source of its matchdays this season.
        links = {}
        if self.instance.pk:
            links = {link.team_id: link for link in self.instance.nuliga_links.all()}
        self.nuliga_teams = list(Team.objects.order_by("name"))
        for team in self.nuliga_teams:
            link = links.get(team.pk)
            self.fields[f"nuliga_{team.pk}"] = forms.URLField(
                required=False,
                max_length=500,
                assume_scheme="https",
                label=_("nuLiga team page"),
                initial=link.team_url if link else "",
                widget=forms.URLInput(attrs={"placeholder": "https://….liga.nu/…/teamPortrait?…"}),
            )
        self.change_labels = {f"nuliga_{t.pk}": f"nuLiga {t.name}" for t in self.nuliga_teams}
        self.nuliga_status = {team_id: link for team_id, link in links.items()}

    def clean(self):
        from app.matchdays.nuliga import NuligaError, check_url

        cleaned = super().clean()
        for team in self.nuliga_teams:
            name = f"nuliga_{team.pk}"
            url = cleaned.get(name)
            if url:
                try:
                    cleaned[name] = check_url(url)
                except NuligaError as exc:
                    self.add_error(name, str(exc))
        return cleaned

    def save_nuliga(self, season) -> list:
        """Store the team pages; returns the links that are new or changed."""
        from app.matchdays.models import NuligaLink

        changed = []
        for team in self.nuliga_teams:
            url = self.cleaned_data.get(f"nuliga_{team.pk}") or ""
            link = NuligaLink.objects.filter(season=season, team=team).first()
            if not url:
                if link is not None:
                    link.delete()
                continue
            if link is None:
                link = NuligaLink(season=season, team=team)
            elif link.team_url == url:
                continue
            link.team_url = url
            link.feed_url = ""
            link.last_sync_at = None
            link.last_error = ""
            link.save()
            changed.append(link)
        return changed


class MatchdayForm(forms.ModelForm):
    """Team, season, opponent, venue, date, description — no participant picker.

    Who played is decided on the detail page ("Add players"): this form only
    edits the matchday itself and never touches the participant list.
    """

    team = forms.ModelChoiceField(queryset=Team.objects.all(), label=_("Team"))
    season = forms.ModelChoiceField(
        queryset=Season.objects.all().order_by("-name"),
        required=False,
        label=_("Season"),
        help_text=_("Every matchday belongs to one season (a closed cash box)."),
    )

    class Meta:
        model = Matchday
        fields: ClassVar[list] = [
            "team",
            "season",
            "opponent",
            "venue",
            "date",
            "start_time",
            "location",
            "description",
            "nuliga_manual",
        ]
        widgets: ClassVar[dict] = {
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            # type="date" strictly requires ISO (YYYY-MM-DD). Without an explicit
            # format the locale decides (de: dd.mm.yyyy), which the browser cannot
            # map onto the date input -> it shows an EMPTY field although the date
            # is stored, and every save then fails with "This field is required."
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    NULIGA_FIELDS: ClassVar[tuple] = ("date", "start_time", "venue", "opponent", "location")

    def __init__(self, *args, user=None, season=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team_locked = False
        if not self.instance.nuliga_uid:
            # Only matchdays imported from nuLiga can be taken out of the import.
            del self.fields["nuliga_manual"]
        # Precedence admin > captain: an Admin who also sits in the Captain
        # group keeps the free team choice (roles are single-valued by design,
        # but the Django admin group editor can produce hybrid accounts).
        if user is not None and user_is_captain(user) and not user_is_penalty_admin(user):
            self.team_locked = True
            self.fields["team"].queryset = Team.objects.filter(pk=user.team_id)
            self.fields["team"].initial = user.team_id
            self.fields["team"].disabled = True
        if not self.instance.pk and season is not None and self.initial.get("season") is None:
            # New matchdays default to the globally active season.
            self.initial["season"] = season.pk

        if not self.team_locked:
            # Only teams active in the matchday's season can be picked; an
            # existing matchday keeps its own team even when it is inactive.
            selectable = teams_for_season(self._roster_season())
            if self.instance.pk:
                selectable = selectable | Team.objects.filter(pk=self.instance.team_id)
            self.fields["team"].queryset = selectable
            if (
                not self.instance.pk
                and user is not None
                and user.team_id is not None
                and selectable.filter(pk=user.team_id).exists()
            ):
                # Default on CREATE: the account's own team (an existing
                # matchday keeps its stored team — that is the model initial).
                self.initial["team"] = user.team_id

    def _roster_season(self):
        """Season whose active teams may be picked (same fallback as ``clean``)."""
        season = None
        if self.is_bound:
            season_pk = self.data.get("season")
            if season_pk:
                season = Season.objects.filter(pk=season_pk).first()
        elif self.initial.get("season"):
            season = Season.objects.filter(pk=self.initial["season"]).first()
        if season is None and self.instance.pk:
            season = self.instance.season
        if season is None:
            season = Season.objects.order_by("-name").first()
        return season

    def clean(self):
        cleaned = super().clean()
        if self.instance.nuliga_uid and not cleaned.get("nuliga_manual"):
            # nuLiga would overwrite the change with the next import.
            for name in self.NULIGA_FIELDS:
                if name in cleaned and cleaned[name] != getattr(self.instance, name):
                    self.add_error(
                        name,
                        _(
                            'Comes from nuLiga. Tick "manage by hand" to keep your '
                            "change - otherwise nuLiga sets it back."
                        ),
                    )
        season = cleaned.get("season")
        if season is None:
            if self.instance.pk:
                # Editing keeps the stored season when the field is empty.
                cleaned["season"] = self.instance.season
            else:
                # New matchdays fall back to the newest season (if any exist).
                cleaned["season"] = Season.objects.order_by("-name").first()
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.team_id is None and self.team_locked and self.fields["team"].initial:
            # Disabled field never posts for captains; restore from initial.
            instance.team = Team.objects.get(pk=self.fields["team"].initial)
        if commit:
            # Participants are NEVER written here — they belong exclusively to
            # the "Add players" editor on the matchday detail page.
            instance.save()
        return instance
