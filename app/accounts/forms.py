"""Account forms — admin user management + per-user settings.

``is_staff`` is derived server-side from the chosen role (H1): Admin -> True,
Captain/Player -> False. ``team`` is an OPTIONAL captaincy assignment: a
Captain may have none yet, an Admin may additionally captain a team, a Player
never gets one (decoupled from the role — see ``clean`` below).

Also home of the allauth login gate (``ACCOUNT_FORMS = {"login": …}``):
``ApprovalLoginForm`` blocks pending/rejected accounts with a clear message.
"""

from typing import ClassVar

from allauth.account.forms import LoginForm as AllauthLoginForm
from allauth.account.forms import SignupForm as AllauthSignupForm
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from app.accounts.models import ApprovalStatus
from app.core.choices import PenaltyNotifyChoice, RoleChoice, ThemeChoice
from app.core.permissions import GROUP_ADMIN, GROUP_CAPTAIN, GROUP_PLAYER
from app.players.models import Player

User = get_user_model()

# Single source of truth: rebuilt from RoleChoice (labels unchanged) so the
# model field choices and every form choice can never drift apart.
# Roles: Admin and User. Captain/cashier of a team are assignments any account
# can hold (team field / cash box), so "Captain" is no role to pick anymore.
ROLE_CHOICES = [
    (RoleChoice.ADMIN.value, RoleChoice.ADMIN.label),
    (RoleChoice.PLAYER.value, RoleChoice.PLAYER.label),
]

# Roles that may hold the optional captaincy (``User.team``) — the edit form
# renders the team dropdown disabled for every other role (see UserUpdateForm).
CAPTAINCY_ROLES = (GROUP_ADMIN, GROUP_CAPTAIN, GROUP_PLAYER)


def name_field(form) -> None:
    """The account's own name: optional, editable after registration too."""
    field = form.fields.get("full_name")
    if field is not None:
        field.label = _("Name")
        field.help_text = _(
            "Only shown for accounts without a linked player (e.g. a club account)."
        )


class ApprovalLoginForm(AllauthLoginForm):
    """Login only for admin-approved accounts (django-allauth login form).

    Wired via ``ACCOUNT_FORMS`` in settings; pending and rejected users get a
    clear error message instead of a generic "wrong password".
    """

    def clean(self):
        cleaned_data = super().clean()
        if not self._errors:
            user = getattr(self, "user", None)
            if user is not None and not user.is_approved:
                if user.approval_status == ApprovalStatus.REQUESTED:
                    # Invitation not completed yet — the account holds no
                    # usable password, but e.g. a password reset by an admin
                    # could get this far; point at the e-mail link instead of
                    # the generic "not approved" text.
                    raise forms.ValidationError(
                        _(
                            "You have been invited but have not completed your registration"
                            " yet. Please use the link in your invitation e-mail."
                        )
                    )
                if user.approval_status == ApprovalStatus.REJECTED:
                    raise forms.ValidationError(
                        _("Your registration has been declined. Please contact the club.")
                    )
                raise forms.ValidationError(
                    _(
                        "Your account has not been approved by an administrator yet. "
                        "Please contact the club."
                    )
                )
        return cleaned_data


class SignupForm(AllauthSignupForm):
    """Self-registration with the name needed for player assignment.

    Wired via ``ACCOUNT_FORMS["signup"]`` (settings). allauth's
    ``BaseSignupForm.save()`` calls ``signup(request, user)`` right after the
    adapter persisted the account — that hook stores the extra field. The
    honeypot/rate-limit behaviour of the parent class is untouched.
    """

    full_name = forms.CharField(
        label=_("First and last name"),
        max_length=150,
        required=True,
        help_text=_("Required to assign your account to your player record."),
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
        error_messages={"required": _("Please enter your first and last name.")},
    )
    # Render order: e-mail, name, passwords — fields not listed (the honeypot
    # allauth appends afterwards) keep their declaration order.
    field_order: ClassVar[list] = ["email", "full_name", "password1", "password2"]

    def signup(self, request, user):
        """Persist ONLY the new field (the adapter already saved the user)."""
        user.full_name = (self.cleaned_data.get("full_name") or "").strip()
        user.save(update_fields=["full_name"])


def unlinked_players_queryset(user=None):
    """Players that are NOT linked to a user account (the link is 1:1).

    When editing ``user``, that user's own current link stays selectable —
    every other already-linked player is hidden.
    """
    queryset = Player.objects.filter(user_account__isnull=True)
    if user is not None and user.pk:
        queryset = Player.objects.filter(Q(user_account__isnull=True) | Q(user_account=user))
    return queryset.order_by("name")


def inviteable_players_queryset():
    """Players that are neither linked to a user nor reserved by an OPEN invitation.

    The single-row ``exclude`` keeps both conditions tied to one invitation
    row (reservation = ``accepted_at IS NULL AND expires_at > now``), so a
    player stays selectable while their own invitation is merely expired.
    Refreshed per request in ``InviteCreateForm.__init__`` — like
    ``unlinked_players_queryset``.
    """
    return (
        Player.objects.filter(user_account__isnull=True)
        .exclude(
            invitations__accepted_at__isnull=True,
            invitations__expires_at__gt=timezone.now(),
        )
        .order_by("name")
    )


ADMIN_AREA_FIELDS = ("admin_elo", "admin_penalty", "admin_portal")


def clean_admin_areas(cleaned: dict) -> dict:
    """Role Admin: the ticked areas (none ticked = every area). Role User: none."""
    if cleaned.get("role") == GROUP_ADMIN:
        if not any(cleaned.get(f) for f in ADMIN_AREA_FIELDS):
            for f in ADMIN_AREA_FIELDS:
                cleaned[f] = True
    else:
        for f in ADMIN_AREA_FIELDS:
            cleaned[f] = False
    return cleaned


def clean_club_account(form, cleaned: dict) -> dict:
    """A club account is a shared login: no admin, no person, no captaincy."""
    if not cleaned.get("is_club_account"):
        return cleaned
    if cleaned.get("role") == GROUP_ADMIN or getattr(form.instance, "is_superuser", False):
        form.add_error("is_club_account", _("A club account cannot be an admin."))
    if cleaned.get("player_link"):
        form.add_error(
            "is_club_account", _("A club account is not a person: remove the linked player.")
        )
    if cleaned.get("team"):
        form.add_error("is_club_account", _("A club account cannot be a team captain."))
    return cleaned


class UserCreateForm(forms.ModelForm):
    role = forms.ChoiceField(choices=ROLE_CHOICES, label=_("Role"), initial=RoleChoice.PLAYER.value)
    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Password confirmation"), widget=forms.PasswordInput)

    class Meta:
        model = User
        fields: ClassVar[list] = [
            "email",
            "full_name",
            "role",
            "is_club_account",
            "admin_elo",
            "admin_penalty",
            "admin_portal",
            "team",
            "player_link",
            "is_active",
            "preferred_language",
            "elo_access",
            "penalty_access",
        ]
        widgets: ClassVar[dict] = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        name_field(self)
        drop_disabled_module_fields(self)
        # Only NOT-yet-linked players may be picked for a NEW user.
        self.fields["player_link"].queryset = unlinked_players_queryset()
        # The team field IS a captaincy — rename it on the CREATE form too,
        # otherwise the model's verbose_name would render a bare "Team".
        self.fields["team"].label = _("Captain in this team")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("A user with this email address already exists."))
        return email

    def clean(self):
        cleaned = super().clean()
        # The team field is a captaincy assignment, NOT a role requirement:
        # optional for Captain, allowed for Admin, never valid for Player.
        return clean_club_account(self, clean_admin_areas(cleaned))

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return password2

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get("password2")
        if password:
            from django.contrib.auth.password_validation import validate_password

            try:
                validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error("password2", error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password2"])
        user.is_staff = self.cleaned_data["role"] == GROUP_ADMIN
        # Accounts created by an admin are usable right away — the approval
        # workflow only applies to self-registration.
        user.approval_status = ApprovalStatus.APPROVED
        if commit:
            user.save()
            role_group = Group.objects.get(name=self.cleaned_data["role"])
            user.groups.set([role_group])
        return user


class InviteCreateForm(forms.ModelForm):
    """Send an invitation: e-mail + pre-assignment payload, no passwords.

    Mirrors ``UserCreateForm`` minus the password fields — the invitee sets
    their own password on the acceptance page. The ``player`` field is an
    ``Invitation`` field (the model spans two models, hence no ``CreateView``)
    and only offers players that are neither linked nor reserved by another
    OPEN invitation.
    """

    role = forms.ChoiceField(choices=ROLE_CHOICES, label=_("Role"), initial=RoleChoice.PLAYER.value)
    player = forms.ModelChoiceField(
        queryset=inviteable_players_queryset(),
        required=False,
        label=_("Linked player"),
        help_text=_(
            "Optional: pre-assigned player — linked to the account when the invitation is accepted."
        ),
    )

    class Meta:
        model = User
        fields: ClassVar[list] = [
            "email",
            "role",
            "team",
            "preferred_language",
            "elo_access",
            "penalty_access",
        ]
        widgets: ClassVar[dict] = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        drop_disabled_module_fields(self)
        # Refresh per request — players may have been linked since import time.
        self.fields["player"].queryset = inviteable_players_queryset()
        # Same captaincy toggle contract as UserUpdateForm: the marker lets
        # user_form.html enable the dropdown for Admin/Captain only; the
        # state lives on the WIDGET (field stays editable for crafted POSTs,
        # clean() enforces the rule server-side).
        effective_role = self.data.get("role") if self.is_bound else self.fields["role"].initial
        attrs = self.fields["team"].widget.attrs
        attrs["data-team-roles"] = ",".join(CAPTAINCY_ROLES)
        if effective_role not in CAPTAINCY_ROLES:
            attrs["disabled"] = True

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        existing = User.objects.filter(email__iexact=email).first()
        if existing is not None:
            if existing.approval_status == ApprovalStatus.REQUESTED:
                raise forms.ValidationError(
                    _("Already invited — cancel or resend the existing invitation.")
                )
            raise forms.ValidationError(_("A user with this email address already exists."))
        return email

    def clean(self):
        cleaned = super().clean()
        # The team is a captaincy: optional for Captain, allowed for Admin,
        # never valid for Player (same rule as UserCreateForm).
        # Server-side reservation guard (the field queryset already enforces
        # it; this keeps the intent explicit if the queryset is ever relaxed).
        player = cleaned.get("player")
        if player is not None and not inviteable_players_queryset().filter(pk=player.pk).exists():
            self.add_error(
                "player",
                _("This player is already reserved by another invitation."),
            )
        return cleaned


class InvitationAcceptForm(forms.Form):
    """Public set-password form of the acceptance link (no username, no e-mail —
    the token fixes the account). Password handling mirrors ``UserCreateForm``:
    match check in ``clean()``, Django's ``validate_password`` in ``_post_clean``.
    """

    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Password confirmation"), widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", _("The two password fields didn't match."))
        return cleaned

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get("password1")
        if password:
            from django.contrib.auth.password_validation import validate_password

            try:
                validate_password(password)
            except forms.ValidationError as error:
                self.add_error("password1", error)


class UserApprovalForm(forms.Form):
    """Single-save approval: approve the user AND link (or create) a player.

    One POST performs the whole review step — the admin neither switches
    pages nor saves twice.
    """

    player = forms.ModelChoiceField(
        queryset=unlinked_players_queryset(),
        required=False,
        label=_("Existing player"),
        help_text=_("Optional: link this account to an existing player."),
    )
    new_player_name = forms.CharField(
        max_length=120,
        required=False,
        label=_("New player"),
        help_text=_("Optional: create a new player and link it immediately."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Refresh per request — players may have been linked since import time.
        self.fields["player"].queryset = unlinked_players_queryset()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("player") and (cleaned.get("new_player_name") or "").strip():
            self.add_error(
                "new_player_name",
                _("Choose an existing player OR enter a new player name — not both."),
            )
        return cleaned


class UserUpdateForm(forms.ModelForm):
    role = forms.ChoiceField(choices=ROLE_CHOICES, label=_("Role"), initial=RoleChoice.PLAYER.value)

    class Meta:
        model = User
        fields: ClassVar[list] = [
            "email",
            "full_name",
            "role",
            "is_club_account",
            "admin_elo",
            "admin_penalty",
            "admin_portal",
            "team",
            "player_link",
            "is_active",
            "preferred_language",
            "elo_access",
            "penalty_access",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        name_field(self)
        drop_disabled_module_fields(self)
        # Only NOT-yet-linked players — plus this user's own current link.
        self.fields["player_link"].queryset = unlinked_players_queryset(self.instance)
        # The team field IS a captaincy — label it accordingly on the edit form.
        self.fields["team"].label = _("Captain in this team")
        if self.instance.pk:
            role = None
            if self.instance.is_admin:
                role = GROUP_ADMIN
            elif self.instance.groups.filter(name=GROUP_CAPTAIN).exists():
                role = GROUP_PLAYER  # legacy captain group -> User role + team
            elif self.instance.is_player:
                role = GROUP_PLAYER
            self.fields["role"].initial = role
            if role == GROUP_ADMIN and not any(
                getattr(self.instance, f) for f in ADMIN_AREA_FIELDS
            ):
                for f in ADMIN_AREA_FIELDS:  # admin from before the areas: everything
                    self.initial[f] = True
        if self.instance.pk and self.instance.is_superuser:
            # The system account (DJANGO_SUPERUSER_EMAIL) can never lose rights.
            self.fields["role"].initial = GROUP_ADMIN
            for name in ("role", "is_active", *ADMIN_AREA_FIELDS):
                if name in self.fields:
                    self.fields[name].disabled = True
                    self.initial[name] = True if name != "role" else GROUP_ADMIN
        # The dropdown is only usable for Captain/Admin accounts (a Player never
        # holds a team). The state is set on the WIDGET only — ``field.disabled``
        # stays False so a crafted POST is still validated against the team/role
        # rule in ``clean()``. ``data-team-roles`` lets user_form.html toggle the
        # dropdown live when the role select changes.
        effective_role = self.data.get("role") if self.is_bound else self.fields["role"].initial
        attrs = self.fields["team"].widget.attrs
        attrs["data-team-roles"] = ",".join(CAPTAINCY_ROLES)
        if effective_role not in CAPTAINCY_ROLES:
            attrs["disabled"] = True

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        duplicate = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists()
        if duplicate:
            raise forms.ValidationError(_("A user with this email address already exists."))
        return email

    def clean(self):
        cleaned = super().clean()
        # Same rule as UserCreateForm: the team is an optional captaincy for
        # Captain/Admin accounts and invalid for the Player role.
        if self.instance.is_superuser:
            return cleaned  # the system account keeps everything (fields are locked)
        return clean_club_account(self, clean_admin_areas(cleaned))

    def save(self, commit=True):
        user = super().save(commit=False)
        role = GROUP_ADMIN if user.is_superuser else self.cleaned_data["role"]
        user.is_staff = role == GROUP_ADMIN
        if commit:
            user.save()
            if user.pk:
                user.groups.set([Group.objects.get(name=role)])
        return user


class EmailChangeForm(forms.Form):
    """A member changes their own login address (confirmed by the password)."""

    email = forms.EmailField(label=_("New e-mail address"), max_length=254)
    password = forms.CharField(label=_("Current password"), widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_email(self):
        from allauth.account.models import EmailAddress

        email = self.cleaned_data["email"].strip().lower()
        if email == (self.user.email or "").lower():
            raise forms.ValidationError(_("This is already your e-mail address."))
        taken = (
            User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists()
            or EmailAddress.objects.filter(email__iexact=email).exclude(user=self.user).exists()
        )
        if taken:
            raise forms.ValidationError(_("A user with this email address already exists."))
        return email

    def clean_password(self):
        password = self.cleaned_data.get("password") or ""
        if not self.user.check_password(password):
            raise forms.ValidationError(_("The password is not correct."))
        return password


class SettingsForm(forms.ModelForm):
    """Language, theme AND the per-user notification preferences.

    The notification block mirrors the mail types a user may switch off:

    * ``penalty_notify_mode``/``penalty_notify_time`` — Off / Quick (collected
      after the coalescing window) / Daily digest at the chosen time,
    * ``repayment_notify``    — a receipt per recorded payment,
    * ``club_news_optin``     — round mails / club information.

    The two booleans are rendered as OFF/subscribe radio groups, so an
    unchecked box is never a hidden "No" — the choice is always visible.
    Transactional mails (invitation, approval, password reset, e-mail
    verification) are deliberately NOT part of this form: they always go out.
    """

    penalty_notify_time = forms.TimeField(
        label=_("Digest time"),
        help_text=_("Only used by the daily digest."),
        input_formats=["%H:%M", "%H:%M:%S"],
        widget=forms.TimeInput(attrs={"type": "time", "step": "300"}, format="%H:%M"),
    )
    repayment_notify = forms.BooleanField(
        required=False,
        label=_("Payment confirmation"),
        widget=forms.RadioSelect(
            choices=((True, _("Abonnieren")), (False, _("Off"))),
        ),
    )
    club_news_optin = forms.BooleanField(
        required=False,
        label=_("Club news / round mails"),
        widget=forms.RadioSelect(
            choices=((True, _("Abonnieren")), (False, _("Off"))),
        ),
    )
    elo_match_notify = forms.BooleanField(
        required=False,
        label=_("Elo match results"),
        widget=forms.RadioSelect(choices=((True, _("Abonnieren")), (False, _("Off")))),
    )
    elo_match_digest = forms.BooleanField(
        required=False,
        label=_("Elo match results as a daily summary"),
    )
    elo_monthly_summary = forms.BooleanField(
        required=False,
        label=_("Monthly Elo summary"),
        widget=forms.RadioSelect(choices=((True, _("Abonnieren")), (False, _("Off")))),
    )

    class Meta:
        model = User
        fields: ClassVar[list] = [
            "full_name",
            "preferred_language",
            "preferred_theme",
            "start_page",
            "penalty_notify_mode",
            "penalty_notify_time",
            "repayment_notify",
            "club_news_optin",
            "elo_match_notify",
            "elo_match_digest",
            "elo_monthly_summary",
        ]
        widgets: ClassVar[dict] = {
            "preferred_language": forms.Select(choices=settings.LANGUAGES),
            "preferred_theme": forms.Select(choices=ThemeChoice.choices),
            "start_page": forms.Select,
            "penalty_notify_mode": forms.RadioSelect,
        }

    PENALTY_FIELDS = ("penalty_notify_mode", "repayment_notify")
    ELO_FIELDS = ("elo_match_notify", "elo_match_digest", "elo_monthly_summary")

    def __init__(self, *args, **kwargs):
        """Only the mails and start pages of modules this account can use."""
        super().__init__(*args, **kwargs)
        name_field(self)
        if self.instance.player_link_id:
            # The player is the name; the admins rename players.
            self.fields.pop("full_name")
        from app.core.access import user_modules

        mods = user_modules(self.instance) if self.instance and self.instance.pk else {}
        if not mods.get("penalty"):
            for name in self.PENALTY_FIELDS:
                self.fields.pop(name, None)
        if not mods.get("elo"):
            for name in self.ELO_FIELDS:
                self.fields.pop(name, None)
        if not mods.get("penalty") and not mods.get("elo"):
            # The digest time serves the penalty AND the Elo daily summary.
            self.fields.pop("penalty_notify_time", None)
        allowed = {"auto"}
        if mods.get("elo"):
            allowed.add("elo")
        if mods.get("penalty"):
            allowed.add("penalty")
        if mods.get("elo") and mods.get("penalty"):
            allowed.add("overview")
        self.fields["start_page"].choices = [
            c for c in self.fields["start_page"].choices if c[0] in allowed
        ]
        # Optional in the POST: an old client without the field keeps the value.
        self.fields["start_page"].required = False
        for name in ("elo_match_notify", "elo_match_digest", "elo_monthly_summary"):
            if name in self.fields and self.is_bound and name not in self.data:
                self.fields[name].disabled = True  # not sent -> keep the stored value

    def clean_start_page(self):
        return self.cleaned_data.get("start_page") or self.instance.start_page or "auto"

    def clean_full_name(self):
        # Not sent (older client) -> keep the stored name instead of blanking it.
        if "full_name" not in self.data:
            return self.instance.full_name
        return (self.cleaned_data.get("full_name") or "").strip()

    def clean(self):
        """A digest without a time is a contradiction — say so, don't guess."""
        cleaned = super().clean()
        mode = cleaned.get("penalty_notify_mode")
        if mode == PenaltyNotifyChoice.DAILY and not cleaned.get("penalty_notify_time"):
            self.add_error(
                "penalty_notify_time",
                _("Choose the time of day for the daily digest."),
            )
        return cleaned


def drop_disabled_module_fields(form) -> None:
    """Module access switches only for modules this installation runs."""
    from app.core.modules import ELO, PENALTY, enabled_modules

    mods = enabled_modules()
    if ELO not in mods:
        form.fields.pop("elo_access", None)
    if PENALTY not in mods:
        form.fields.pop("penalty_access", None)
    for name, help_text in (
        ("elo_access", _("Ranking, statistics and entering matches.")),
        ("penalty_access", _("Penalties, payments and the financial overview.")),
    ):
        if name in form.fields:
            form.fields[name].help_text = help_text
