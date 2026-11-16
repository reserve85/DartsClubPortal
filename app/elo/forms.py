"""Forms of the Elo module (match entry/editing, Elo players)."""

import re

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from app.elo.conf import elo_setting
from app.elo.models import EloProfile
from app.elo.services.validation import VALID_BEST_OF
from app.players.models import Player

_NUM_LIST = re.compile(r"^[\d\s,;]*$")


class IntListField(forms.CharField):
    """ "120, 100" -> [120, 100] (empty -> [])."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault(
            "widget",
            forms.TextInput(attrs={"inputmode": "numeric", "placeholder": _("e.g. 120, 100")}),
        )
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        value = (super().to_python(value) or "").strip()
        if not value:
            return []
        if not _NUM_LIST.match(value):
            raise forms.ValidationError(_("Only numbers separated by commas."))
        return [int(x) for x in re.split(r"[\s,;]+", value) if x]

    def prepare_value(self, value):
        if isinstance(value, list | tuple):
            return ", ".join(str(v) for v in value)
        return value


def _elo_players(include_disabled=False):
    qs = Player.objects.filter(elo__isnull=False).select_related("elo").order_by("name")
    if not include_disabled:
        qs = qs.filter(elo__disabled=False)
    return qs


class PlayerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name


def _stat_fields():
    return {
        "a_180s": forms.IntegerField(label=_("180s"), required=False, min_value=0, max_value=63),
        "b_180s": forms.IntegerField(label=_("180s"), required=False, min_value=0, max_value=63),
        "a_high_finishes": IntListField(label=_("High finishes")),
        "b_high_finishes": IntListField(label=_("High finishes")),
        "a_low_darts": IntListField(label=_("Low darts")),
        "b_low_darts": IntListField(label=_("Low darts")),
        "a_average": forms.DecimalField(
            label=_("Average"), required=False, min_value=0, max_value=180, decimal_places=2
        ),
        "b_average": forms.DecimalField(
            label=_("Average"), required=False, min_value=0, max_value=180, decimal_places=2
        ),
    }


class _StatsMixin:
    STAT_KEYS = (
        "a_180s",
        "b_180s",
        "a_high_finishes",
        "b_high_finishes",
        "a_low_darts",
        "b_low_darts",
        "a_average",
        "b_average",
    )

    def stats(self) -> dict:
        out = {}
        for key in self.STAT_KEYS:
            value = self.cleaned_data.get(key)
            if key.endswith("180s"):
                value = value or 0
            elif key.endswith("average"):
                value = float(value) if value is not None else None
            out[key] = value
        return out


class MatchForm(_StatsMixin, forms.Form):
    player_a = PlayerChoiceField(queryset=Player.objects.none(), label=_("Player A"))
    player_b = PlayerChoiceField(queryset=Player.objects.none(), label=_("Player B"))
    match_date = forms.DateField(
        label=_("Date"), widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    best_of_legs = forms.TypedChoiceField(
        label=_("Format"),
        coerce=int,
        choices=[(n, _("Best of %(n)s") % {"n": n}) for n in VALID_BEST_OF],
    )
    score_a = forms.IntegerField(label=_("Legs"), min_value=0, max_value=11)
    score_b = forms.IntegerField(label=_("Legs"), min_value=0, max_value=11)
    force = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(_stat_fields())
        qs = _elo_players()
        self.fields["player_a"].queryset = qs
        self.fields["player_b"].queryset = qs
        self.fields["match_date"].initial = timezone.localdate()
        self.fields["best_of_legs"].initial = elo_setting("BEST_OF_LEGS")

    def clean(self):
        cleaned = super().clean()
        a, b = cleaned.get("player_a"), cleaned.get("player_b")
        if a and b and a.pk == b.pk:
            self.add_error("player_b", _("Choose two different players."))
        return cleaned


class MatchEditForm(_StatsMixin, forms.Form):
    match_date = forms.DateField(
        label=_("Date"), widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    best_of_legs = forms.TypedChoiceField(
        label=_("Format"),
        coerce=int,
        choices=[(n, _("Best of %(n)s") % {"n": n}) for n in VALID_BEST_OF],
    )
    score_a = forms.IntegerField(label=_("Legs"), min_value=0, max_value=11)
    score_b = forms.IntegerField(label=_("Legs"), min_value=0, max_value=11)
    force = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, match=None, **kwargs):
        if match is not None and "initial" not in kwargs:
            kwargs["initial"] = {
                "match_date": match.date,
                "best_of_legs": match.best_of_legs,
                "score_a": match.score_a,
                "score_b": match.score_b,
                **{k: getattr(match, k) for k in self.STAT_KEYS},
            }
        super().__init__(*args, **kwargs)
        self.fields.update(_stat_fields())


class EloPlayerAddForm(forms.Form):
    existing = forms.ModelChoiceField(
        queryset=Player.objects.none(),
        required=False,
        label=_("Existing person"),
        empty_label=_("— new person —"),
        help_text=_(
            "Pick a person who is already in the club portal (e.g. from the penalty module)."
        ),
    )
    name = forms.CharField(label=_("Name"), required=False, max_length=120)
    start_elo = forms.IntegerField(label=_("Start Elo"), min_value=100, max_value=4000)
    entry_date = forms.DateField(
        label=_("Entry date"),
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text=_("The player is part of the ranking from this day on."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["existing"].queryset = Player.objects.filter(elo__isnull=True).order_by("name")
        self.fields["start_elo"].initial = elo_setting("DEFAULT_ELO")
        self.fields["entry_date"].initial = timezone.localdate()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("existing") and not (cleaned.get("name") or "").strip():
            self.add_error("name", _("Pick an existing person or enter a name."))
        return cleaned


class EloPlayerEditForm(forms.Form):
    name = forms.CharField(label=_("Name"), max_length=120)
    start_elo = forms.IntegerField(
        label=_("Start Elo"),
        min_value=100,
        max_value=4000,
        help_text=_("Changing it recalculates every match of this player."),
    )
    entry_date = forms.DateField(
        label=_("Entry date"), widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )

    def __init__(self, *args, profile: EloProfile, **kwargs):
        kwargs.setdefault(
            "initial",
            {
                "name": profile.player.name,
                "start_elo": profile.start_elo,
                "entry_date": profile.entry_date,
            },
        )
        super().__init__(*args, **kwargs)
