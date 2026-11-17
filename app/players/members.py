"""Members: one place for every person of the club.

A member is a ``Player`` - with or without a login. The three pages bring
together what used to live on three admin pages:

* ``/players/``            list of every person (teams, Elo, account),
* ``/players/create/``     new member: name, team, Elo start and invitation
  in one form,
* ``/players/<pk>/edit/``  one person: basics, teams of the season, Elo and
  account (invite / link / unlink).

Every section is guarded by the area it belongs to: teams by the Penalty
area (captains: their own team), Elo by the Elo area, the account by the
Portal area. Captains keep creating and editing the players of their team.
"""

from datetime import date

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from inertia import render as inertia_render

from app.accounts.models import ApprovalStatus, Invitation
from app.core.inertia_utils import form_errors, request_data
from app.core.models import AuditAction
from app.core.modules import ELO, PENALTY, enabled_modules
from app.core.permissions import (
    GROUP_PLAYER,
    user_can_edit_player,
    user_is_admin,
    user_is_captain,
    user_is_elo_admin,
    user_is_penalty_admin,
    user_is_portal_admin,
)
from app.core.services import log_action
from app.matchdays.services import season_for_request
from app.players.models import Player, PlayerTeam
from app.players.services import assign_teams
from app.teams.services import teams_for_season

User = get_user_model()


# ---------------------------------------------------------------- permissions
def can_manage_teams(user) -> bool:
    return PENALTY in enabled_modules() and (user_is_penalty_admin(user) or user_is_captain(user))


def can_manage_elo(user) -> bool:
    return ELO in enabled_modules() and user_is_elo_admin(user)


def can_manage_accounts(user) -> bool:
    return user_is_portal_admin(user)


def editable_teams(user, season) -> list:
    """Teams of the season this account may assign players to."""
    if PENALTY not in enabled_modules():
        return []
    teams = list(teams_for_season(season).order_by("name"))
    if user_is_penalty_admin(user):
        return teams
    if user_is_captain(user) and user.team_id:
        return [t for t in teams if t.pk == user.team_id]
    return []


def _name_taken(name: str, exclude_pk=None) -> bool:
    qs = Player.objects.filter(name__iexact=name.strip())
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def _open_invitation(player):
    return (
        Invitation.objects.select_related("user")
        .filter(player=player, accepted_at__isnull=True, expires_at__gt=timezone.now())
        .order_by("-pk")
        .first()
    )


def _clean_invite_email(email: str) -> str:
    email = (email or "").strip().lower()
    existing = User.objects.filter(email__iexact=email).first()
    if existing is not None:
        if existing.approval_status == ApprovalStatus.REQUESTED:
            raise forms.ValidationError(
                _("Already invited — cancel or resend the existing invitation.")
            )
        raise forms.ValidationError(_("A user with this email address already exists."))
    return email


def _invite(player, *, email, language, actor):
    """Create the invitation (login reserved) and mail it after the commit."""
    from app.accounts.services import create_invitation

    invitation = create_invitation(
        email=email,
        role=GROUP_PLAYER,
        team=None,
        player=player,
        language=language,
        invited_by=actor,
    )
    log_action(
        AuditAction.USER_INVITE_SENT,
        user=actor,
        target=invitation.user,
        metadata={"email": email, "role": invitation.role, "player_id": player.pk},
    )
    return invitation


def _send(invitation, request) -> None:
    from app.notifications.services import notification_service

    if notification_service.send_invitation(invitation, request=request) == 0:
        messages.warning(
            request, _("Invitation created, but the e-mail could not be sent — use Resend.")
        )
    else:
        messages.success(
            request, _("Invitation sent to %(email)s.") % {"email": invitation.user.email}
        )


# ---------------------------------------------------------------- list
class MemberListView(LoginRequiredMixin, View):
    """Every person of the club - the admin's starting point."""

    def get(self, request):
        if not user_is_admin(request.user):
            raise PermissionDenied
        from app.elo.models import EloProfile
        from app.players.avatars import avatars_for

        season = season_for_request(request)
        assignments = PlayerTeam.objects.select_related("team")
        if season is not None:
            assignments = assignments.filter(season=season)
        players = list(
            Player.objects.order_by("name").prefetch_related(
                Prefetch("team_assignments", queryset=assignments, to_attr="season_teams")
            )
        )
        profiles = {p.player_id: p for p in EloProfile.objects.all()}
        accounts = {u.player_link_id: u for u in User.objects.filter(player_link__isnull=False)}
        invited = {
            i.player_id: i
            for i in Invitation.objects.select_related("user").filter(
                player__isnull=False, accepted_at__isnull=True, expires_at__gt=timezone.now()
            )
        }
        avatars = avatars_for([p.pk for p in players])
        elo_on = ELO in enabled_modules()

        def row(p):
            prof = profiles.get(p.pk) if elo_on else None
            account = accounts.get(p.pk)
            invitation = invited.get(p.pk)
            if account is not None:
                acc = {"state": "linked", "email": account.email, "active": account.is_active}
            elif invitation is not None:
                acc = {"state": "invited", "email": invitation.user.email, "active": True}
            else:
                acc = {"state": "none", "email": "", "active": False}
            return {
                "id": p.pk,
                "name": p.name,
                "active": p.active,
                "avatar": avatars.get(p.pk, ""),
                "teams": [a.team.name for a in p.season_teams],
                "elo": (
                    {"current": round(prof.current_elo), "disabled": prof.disabled}
                    if prof is not None
                    else None
                ),
                "account": acc,
                "editUrl": reverse("players:player_update", args=[p.pk]),
            }

        user = request.user
        teams = editable_teams(user, season)
        portal = can_manage_accounts(user)
        return inertia_render(
            request,
            "Members/List",
            props={
                "members": [row(p) for p in players],
                "season": season.name if season else "",
                "eloEnabled": elo_on,
                "penaltyEnabled": PENALTY in enabled_modules(),
                "can": {"elo": can_manage_elo(user), "invite": portal},
                # Quick add: the team of the season (preselected when there is one)
                "teams": [{"value": str(t.pk), "label": t.name} for t in teams],
                "defaultTeam": str(teams[0].pk) if len(teams) == 1 else "",
                "languages": [{"value": c, "label": str(n)} for c, n in settings.LANGUAGES],
                "language": settings.LANGUAGE_CODE[:2],
                "pendingApprovals": (
                    User.objects.filter(approval_status=ApprovalStatus.PENDING).count()
                    if portal
                    else 0
                ),
                "accountsWithoutPlayer": (
                    User.objects.filter(player_link__isnull=True, is_active=True)
                    .exclude(approval_status__in=[ApprovalStatus.REQUESTED, ApprovalStatus.PENDING])
                    .count()
                    if portal
                    else 0
                ),
                "urls": {
                    "create": reverse("players:player_create"),
                    "quickAdd": reverse("players:member_quick_add"),
                    "users": reverse("accounts:user_list") if portal else None,
                    "approvals": reverse("accounts:approval_list") if portal else None,
                    "list": reverse("players:player_list"),
                },
            },
        )


class MemberQuickAddView(LoginRequiredMixin, View):
    """Type names, press Enter: one member per line, with the usual defaults.

    Defaults: the chosen team of the season, the Elo ranking at the default
    start Elo (Elo admins). Existing names are skipped and reported.
    """

    def post(self, request):
        user = request.user
        if not user_is_admin(user):
            raise PermissionDenied
        data = request_data(request)
        season = season_for_request(request)
        teams = {t.pk: t for t in editable_teams(user, season)}
        try:
            team = teams.get(int(data.get("team") or 0))
        except (TypeError, ValueError):
            team = None
        with_elo = can_manage_elo(user) and str(data.get("elo")).lower() in ("1", "true", "on")
        names, seen = [], set()
        for raw in str(data.get("names") or "").replace(",", "\n").splitlines():
            name = " ".join(raw.split())[:120]
            if name and name.lower() not in seen:
                seen.add(name.lower())
                names.append(name)
        created, skipped = [], []
        for name in names:
            if _name_taken(name):
                skipped.append(name)
                continue
            try:
                with transaction.atomic():
                    player = Player.objects.create(name=name)
                    if team is not None:
                        assign_teams(player, [team], season=season)
                    log_action(
                        AuditAction.PLAYER_CREATED,
                        user=user,
                        target=player,
                        metadata={"quick_add": True, "team_id": team.pk if team else None},
                    )
                    if with_elo:
                        from app.elo.services import players as player_service

                        player_service.add_to_ranking(player=player, user=user)
            except ValidationError:
                skipped.append(name)
                continue
            created.append(name)
        if created:
            messages.success(
                request,
                _("Added: %(names)s") % {"names": ", ".join(created)},
            )
        if skipped:
            messages.warning(
                request,
                _("Already there, skipped: %(names)s") % {"names": ", ".join(skipped)},
            )
        if not names:
            messages.warning(request, _("Please enter a name."))
        return redirect("players:player_list")


# ---------------------------------------------------------------- create
class MemberCreateForm(forms.Form):
    name = forms.CharField(max_length=120)
    team = forms.IntegerField(required=False)
    elo = forms.BooleanField(required=False)
    start_elo = forms.IntegerField(required=False, min_value=100, max_value=4000)
    entry_date = forms.DateField(required=False, input_formats=["%Y-%m-%d"])
    invite = forms.BooleanField(required=False)
    email = forms.EmailField(required=False, max_length=254)
    language = forms.ChoiceField(choices=settings.LANGUAGES, required=False)

    def __init__(self, *args, teams=(), can_elo=False, can_invite=False, captain_team=None, **kw):
        super().__init__(*args, **kw)
        self.teams = {t.pk: t for t in teams}
        self.can_elo, self.can_invite, self.captain_team = can_elo, can_invite, captain_team

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError(_("Please enter a name."))
        if _name_taken(name):
            raise forms.ValidationError(_("A member with this name already exists."))
        return name

    def clean_team(self):
        pk = self.cleaned_data.get("team")
        if self.captain_team is not None:
            return self.captain_team  # captains create players of their own team only
        if pk in (None, ""):
            return None
        if pk not in self.teams:
            raise forms.ValidationError(_("Choose a valid team."))
        return self.teams[pk]

    def clean(self):
        cleaned = super().clean()
        if not self.can_elo:
            cleaned["elo"] = False
        # A filled-in e-mail address IS the invitation (no extra switch).
        if cleaned.get("email"):
            cleaned["invite"] = True
        if not self.can_invite:
            cleaned["invite"] = False
        entry = cleaned.get("entry_date")
        if cleaned.get("elo") and entry and entry > timezone.localdate():
            self.add_error("entry_date", _("The entry date cannot be in the future."))
        if cleaned.get("invite") and "email" not in self.errors:
            if not cleaned.get("email"):
                self.add_error("email", _("Please enter an e-mail address."))
            else:
                try:
                    cleaned["email"] = _clean_invite_email(cleaned["email"])
                except forms.ValidationError as exc:
                    self.add_error("email", exc)
        return cleaned


class MemberCreateView(LoginRequiredMixin, View):
    """New member in one go: name, team of the season, Elo start, invitation."""

    def _allowed(self, user):
        if not (user_is_admin(user) or user_is_captain(user)):
            raise PermissionDenied

    def _captain_team(self, user, season):
        if user_is_penalty_admin(user) or user_is_admin(user):
            return None
        teams = editable_teams(user, season)
        return teams[0] if teams else None

    def _props(self, request, season, form=None):
        from app.elo.conf import elo_setting

        user = request.user
        teams = editable_teams(user, season)
        captain_team = self._captain_team(user, season)
        return {
            "season": season.name if season else "",
            "teams": [{"value": str(t.pk), "label": t.name} for t in teams],
            "defaultTeam": str(teams[0].pk) if len(teams) == 1 else "",
            "captainTeam": captain_team.name if captain_team else None,
            "canElo": can_manage_elo(user),
            "canInvite": can_manage_accounts(user),
            "languages": [{"value": c, "label": str(n)} for c, n in settings.LANGUAGES],
            "defaults": {
                "startElo": elo_setting("DEFAULT_ELO") if can_manage_elo(user) else None,
                "entryDate": timezone.localdate().isoformat(),
                "language": settings.LANGUAGE_CODE[:2],
            },
            "today": timezone.localdate().isoformat(),
            "backUrl": (
                reverse("players:player_list")
                if user_is_admin(user)
                else reverse("teams:team_list")
            ),
            "errors": form_errors(form) if form is not None else {},
        }

    def get(self, request):
        self._allowed(request.user)
        season = season_for_request(request)
        return inertia_render(request, "Members/Create", props=self._props(request, season))

    def post(self, request):
        self._allowed(request.user)
        user = request.user
        season = season_for_request(request)
        form = MemberCreateForm(
            request_data(request),
            teams=editable_teams(user, season),
            can_elo=can_manage_elo(user),
            can_invite=can_manage_accounts(user),
            captain_team=self._captain_team(user, season),
        )
        if not form.is_valid():
            return inertia_render(
                request, "Members/Create", props=self._props(request, season, form)
            )
        d = form.cleaned_data
        invitation = None
        try:
            with transaction.atomic():
                player = Player.objects.create(name=d["name"])
                if d.get("team") is not None:
                    assign_teams(player, [d["team"]], season=season)
                log_action(
                    AuditAction.PLAYER_CREATED,
                    user=user,
                    target=player,
                    metadata={
                        "season_id": season.pk if season else None,
                        "team_id": d["team"].pk if d.get("team") else None,
                    },
                )
                if d.get("elo"):
                    from app.elo.services import players as player_service

                    player_service.add_to_ranking(
                        player=player,
                        start_elo=d.get("start_elo"),
                        entry_date=d.get("entry_date") or timezone.localdate(),
                        user=user,
                    )
                if d.get("invite"):
                    invitation = _invite(
                        player,
                        email=d["email"],
                        language=d.get("language") or settings.LANGUAGE_CODE[:2],
                        actor=user,
                    )
        except ValidationError as exc:
            for msg in exc.messages:
                form.add_error(None, msg)
            return inertia_render(
                request, "Members/Create", props=self._props(request, season, form)
            )
        messages.success(request, _("%(name)s was added.") % {"name": player.name})
        if invitation is not None:
            _send(invitation, request)
        if user_is_admin(user):
            return redirect("players:player_update", pk=player.pk)
        return redirect("teams:team_list")


# ---------------------------------------------------------------- one member
class MemberEditView(LoginRequiredMixin, View):
    """One person: basics, teams of the season, Elo and account."""

    def _player(self, request, pk):
        player = get_object_or_404(Player, pk=pk)
        if not user_can_edit_player(request.user, player):
            raise PermissionDenied
        return player

    def _props(self, request, player, errors=None):
        from app.elo.conf import elo_setting
        from app.elo.models import EloProfile
        from app.elo.services import players as player_service
        from app.players.avatars import avatars_for

        user = request.user
        season = season_for_request(request)
        current = set(
            PlayerTeam.objects.filter(player=player, season=season).values_list(
                "team_id", flat=True
            )
        )
        editable = {t.pk for t in editable_teams(user, season)}
        team_rows = (
            [
                {
                    "id": t.pk,
                    "name": t.name,
                    "checked": t.pk in current,
                    "editable": t.pk in editable,
                }
                for t in teams_for_season(season).order_by("name")
            ]
            if PENALTY in enabled_modules()
            else []
        )

        elo = None
        if can_manage_elo(user):
            profile = EloProfile.objects.filter(player=player).first()
            first = player_service.first_match_date(player.pk) if profile else None
            elo = {
                "profile": (
                    {
                        "current": round(profile.current_elo),
                        "start": profile.start_elo,
                        "entryDate": profile.entry_date.isoformat(),
                        "disabled": profile.disabled,
                        "firstMatch": first.isoformat() if first else None,
                        "editUrl": reverse("elo:player_edit", args=[player.pk]),
                        "statsUrl": reverse("elo:player_detail", args=[player.pk]),
                    }
                    if profile
                    else None
                ),
                "defaults": {
                    "startElo": elo_setting("DEFAULT_ELO"),
                    "entryDate": timezone.localdate().isoformat(),
                },
            }

        account = None
        if can_manage_accounts(user):
            linked = User.objects.filter(player_link=player).first()
            invitation = None if linked else _open_invitation(player)
            linkable = (
                User.objects.filter(player_link__isnull=True, is_active=True)
                .exclude(approval_status__in=[ApprovalStatus.REQUESTED, ApprovalStatus.REJECTED])
                .order_by("email")
            )
            account = {
                "user": (
                    {
                        "email": linked.email,
                        "active": linked.is_active,
                        "lastLogin": linked.last_login.isoformat() if linked.last_login else None,
                        "editUrl": reverse("accounts:user_update", args=[linked.pk]),
                    }
                    if linked
                    else None
                ),
                "invitation": (
                    {
                        "email": invitation.user.email,
                        "expires": invitation.expires_at.isoformat(),
                        "manageUrl": reverse("accounts:invite_list"),
                    }
                    if invitation
                    else None
                ),
                "linkable": [
                    {
                        "value": str(u.pk),
                        "label": u.full_name and f"{u.full_name} · {u.email}" or u.email,
                    }
                    for u in linkable
                ],
                "languages": [{"value": c, "label": str(n)} for c, n in settings.LANGUAGES],
                "language": settings.LANGUAGE_CODE[:2],
            }

        return {
            "player": {
                "id": player.pk,
                "name": player.name,
                "active": player.active,
                "avatar": avatars_for([player.pk]).get(player.pk, ""),
                "detailUrl": reverse("players:player_detail", args=[player.pk]),
            },
            "canPicture": user_is_admin(user),
            "season": season.name if season else "",
            "teams": team_rows,
            "elo": elo,
            "account": account,
            "url": reverse("players:player_update", args=[player.pk]),
            "backUrl": (
                reverse("players:player_list")
                if user_is_admin(user)
                else reverse("teams:team_list")
            ),
            "errors": errors or {},
        }

    def get(self, request, pk):
        player = self._player(request, pk)
        return inertia_render(request, "Members/Edit", props=self._props(request, player))

    def post(self, request, pk):
        player = self._player(request, pk)
        data = request_data(request)
        section = data.get("section")
        handler = {
            "basics": self._basics,
            "teams": self._teams,
            "elo": self._elo,
            "account": self._account,
        }.get(section)
        # Quick actions from the list come back to the list (``next``).
        nxt = str(data.get("next") or "")
        back = nxt if nxt.startswith("/") and not nxt.startswith("//") else None
        if handler is None:
            return redirect(back or reverse("players:player_update", args=[player.pk]))
        errors = handler(request, player, data)
        if errors and back:
            messages.error(request, " ".join(str(e) for e in errors.values()))
            return redirect(back)
        if errors:
            return inertia_render(
                request, "Members/Edit", props=self._props(request, player, {section: errors})
            )
        return redirect(back or reverse("players:player_update", args=[player.pk]))

    # -- sections -------------------------------------------------------------
    def _basics(self, request, player, data):
        from app.elo.models import EloProfile
        from app.elo.services import players as player_service

        name = (data.get("name") or "").strip()
        active = str(data.get("active")).lower() in ("1", "true", "on")
        if not name:
            return {"name": _("Please enter a name.")}
        if _name_taken(name, exclude_pk=player.pk):
            return {"name": _("A member with this name already exists.")}
        profile = EloProfile.objects.filter(player=player).first()
        try:
            if profile is not None and name != player.name:
                player_service.update_profile(profile, name=name, user=request.user)
                player.refresh_from_db()
            player.name = name
            player.active = active
            player.save(update_fields=["name", "active"])
        except ValidationError as exc:
            return {"name": " ".join(exc.messages)}
        log_action(AuditAction.PLAYER_UPDATED, user=request.user, target=player)
        messages.success(request, _("Saved."))
        return None

    def _teams(self, request, player, data):
        season = season_for_request(request)
        editable = {t.pk: t for t in editable_teams(request.user, season)}
        if not editable:
            raise PermissionDenied
        wanted = set()
        for value in data.get("teams") or []:
            try:
                wanted.add(int(value))
            except (TypeError, ValueError):
                continue
        current = {
            a.team_id: a.team
            for a in PlayerTeam.objects.filter(player=player, season=season).select_related("team")
        }
        # Only the teams this account may manage change; the others stay.
        final = {pk: t for pk, t in current.items() if pk not in editable}
        final.update({pk: editable[pk] for pk in wanted if pk in editable})
        if set(final) != set(current):
            assign_teams(player, list(final.values()), season=season)
            log_action(
                AuditAction.PLAYER_UPDATED,
                user=request.user,
                target=player,
                metadata={"season_id": season.pk if season else None, "teams": sorted(final)},
            )
        messages.success(request, _("Teams saved."))

    def _elo(self, request, player, data):
        from app.elo.models import EloProfile
        from app.elo.services import players as player_service

        if not can_manage_elo(request.user):
            raise PermissionDenied
        action = data.get("action")
        profile = EloProfile.objects.filter(player=player).first()
        try:
            if action == "add" and profile is None:
                start = data.get("start_elo")
                try:
                    start = int(start) if start not in (None, "") else None
                except (TypeError, ValueError):
                    return {"start_elo": _("Enter a whole number.")}
                if start is not None and not 100 <= start <= 4000:
                    return {"start_elo": _("Between 100 and 4000.")}
                raw = data.get("entry_date") or ""
                try:
                    entry = date.fromisoformat(raw) if raw else timezone.localdate()
                except ValueError:
                    return {"entry_date": _("Enter a valid date.")}
                player_service.add_to_ranking(
                    player=player, start_elo=start, entry_date=entry, user=request.user
                )
                messages.success(
                    request, _("%(name)s is now in the Elo ranking.") % {"name": player.name}
                )
            elif action == "toggle" and profile is not None:
                if profile.disabled:
                    player_service.reactivate(profile, user=request.user)
                    messages.success(request, _("%(name)s can play again.") % {"name": player.name})
                else:
                    player_service.disable(profile, user=request.user)
                    messages.success(
                        request,
                        _("%(name)s is disabled: stays in the ranking, cannot play new matches.")
                        % {"name": player.name},
                    )
        except ValidationError as exc:
            return {"form": " ".join(exc.messages)}
        return None

    def _account(self, request, player, data):
        if not can_manage_accounts(request.user):
            raise PermissionDenied
        action = data.get("action")
        linked = User.objects.filter(player_link=player).first()
        if action == "invite" and linked is None:
            if _open_invitation(player) is not None:
                return {"email": _("This player is already reserved by another invitation.")}
            try:
                email = _clean_invite_email(data.get("email") or "")
                forms.EmailField().clean(email)
            except forms.ValidationError as exc:
                return {"email": " ".join(exc.messages)}
            language = data.get("language") or settings.LANGUAGE_CODE[:2]
            if language not in dict(settings.LANGUAGES):
                language = settings.LANGUAGE_CODE[:2]
            with transaction.atomic():
                invitation = _invite(player, email=email, language=language, actor=request.user)
            _send(invitation, request)
        elif action == "link" and linked is None:
            try:
                target = User.objects.get(
                    pk=int(data.get("user") or 0), player_link__isnull=True, is_active=True
                )
            except (User.DoesNotExist, ValueError, TypeError):
                return {"user": _("Choose an account.")}
            target.player_link = player
            target.save(update_fields=["player_link"])
            log_action(
                AuditAction.USER_UPDATED,
                user=request.user,
                target=target,
                metadata={"player_link": player.pk},
            )
            messages.success(
                request,
                _("%(email)s is now linked to %(name)s.")
                % {"email": target.email, "name": player.name},
            )
        elif action == "unlink" and linked is not None:
            linked.player_link = None
            linked.save(update_fields=["player_link"])
            log_action(
                AuditAction.USER_UPDATED,
                user=request.user,
                target=linked,
                metadata={"player_link": None, "was": player.pk},
            )
            messages.success(request, _("The account is no longer linked."))
        return None
