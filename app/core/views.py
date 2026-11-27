"""Core views shared across the project (health, imprint, audit, seasons)."""

from decimal import Decimal
from typing import ClassVar

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from inertia import render as inertia_render

from app.core.inertia_utils import form_errors, form_schema
from app.core.models import AuditAction, AuditLog
from app.core.permissions import GROUP_ADMIN, GroupRequiredMixin
from app.core.services import form_changes, log_action
from app.core.utils import numeric_pk, safe_next_url
from app.matchdays.forms import SeasonForm
from app.matchdays.models import Season
from app.matchdays.services import set_active_season
from app.penalties.services import season_open_balance
from app.players.services import bind_unassigned_memberships


class HealthView(View):
    """Docker healthcheck endpoint — plain URL, outside i18n patterns."""

    def get(self, request):
        return JsonResponse({"status": "ok"})


class HomeView(LoginRequiredMixin, View):
    """ "/" forwards to the user's start page (Elo ranking by default)."""

    def get(self, request):
        from app.core.access import start_url

        return redirect(start_url(request.user))


class ScheduleView(LoginRequiredMixin, View):
    """The matchdays of every team of the season, read-only, for every account."""

    def get(self, request):
        from app.core.permissions import user_can_manage_team
        from app.matchdays.calendar import calendar_links
        from app.matchdays.models import Matchday
        from app.matchdays.services import season_for_request
        from app.players.models import PlayerTeam
        from app.teams.services import teams_for_season

        season = season_for_request(request)
        teams = list(teams_for_season(season).order_by("name"))
        user = request.user
        own = {user.team_id} if user.team_id else set()
        player = getattr(user, "player_link", None)
        if player is not None and season is not None:
            own |= set(
                PlayerTeam.objects.filter(player=player, season=season).values_list(
                    "team_id", flat=True
                )
            )
        show_past = request.GET.get("past") == "1"
        today = timezone.localdate()
        rows = Matchday.objects.filter(team__in=teams).select_related("team")
        if season is not None:
            rows = rows.filter(season=season)
        if not show_past:
            rows = rows.filter(date__gte=today)
        manage = {t.pk: user_can_manage_team(user, t) for t in teams}
        props = {
            "season": season.name if season else "",
            "showPast": show_past,
            "teams": [{"id": t.pk, "name": t.name, "own": t.pk in own} for t in teams],
            "rows": [
                {
                    "id": m.pk,
                    "date": m.date.isoformat(),
                    "time": m.start_time.strftime("%H:%M") if m.start_time else "",
                    "teamId": m.team_id,
                    "team": m.team.name,
                    "opponent": m.opponent,
                    "venue": m.get_venue_display(),
                    "home": m.venue == "home",
                    "location": m.location,
                    "removed": m.nuliga_removed,
                    "isToday": m.date == today,
                    "isPast": m.date < today,
                    "url": reverse("matchdays:matchday_detail", args=[m.pk])
                    if manage.get(m.team_id)
                    else None,
                }
                for m in rows.order_by("date", "start_time", "team__name")
            ],
            "calendars": calendar_links(request, teams, own),
        }
        return inertia_render(request, "Schedule", props=props)


class OverviewView(LoginRequiredMixin, View):
    """ "My overview": one card per module the user may use."""

    def get(self, request):
        from inertia import render as inertia_render

        from app.core.overview import build_overview

        return inertia_render(request, "Overview", props=build_overview(request.user, request))


class RightsView(LoginRequiredMixin, View):
    """ "Who may do what": the role matrix plus what THIS account can do."""

    def get(self, request):
        from app.core.access import user_modules
        from app.core.permissions import user_admin_scopes, user_is_admin
        from app.teams.models import TeamCashier

        user = request.user
        cashier_of = list(
            TeamCashier.objects.filter(user=user, valid_to__isnull=True)
            .select_related("team")
            .values_list("team__name", flat=True)
        )
        props = {
            "me": {
                "role": user.role or "",
                "isAdmin": user_is_admin(user),
                "adminScopes": sorted(user_admin_scopes(user)),
                "captainOf": user.team.name if user.team_id else None,
                "cashierOf": cashier_of,
                "hasPlayer": user.player_link_id is not None,
                "modules": user_modules(user),
            }
        }
        return inertia_render(request, "Rights", props=props)


def _contact() -> dict:
    """Imprint / privacy contact data from the CONTACT_* / IMPRINT_* settings."""
    from django.conf import settings

    return {
        "company": settings.CONTACT_COMPANY,
        "name": settings.CONTACT_NAME,
        "street": settings.CONTACT_STREET,
        "city": settings.CONTACT_CITY,
        "email": settings.CONTACT_EMAIL,
        "imprintName": settings.IMPRINT_NAME,
        "imprintUrl": settings.IMPRINT_URL,
    }


class ImprintView(View):
    """Imprint page driven by CONTACT_* / IMPRINT_* settings (public)."""

    def get(self, request):
        return inertia_render(request, "Legal", props={"kind": "imprint", "contact": _contact()})


class PrivacyView(View):
    """Privacy Policy page driven by CONTACT_* settings (public)."""

    def get(self, request):
        return inertia_render(request, "Legal", props={"kind": "privacy", "contact": _contact()})


class AuditLogListView(GroupRequiredMixin, LoginRequiredMixin, View):
    """Admin-only, paginated, filterable audit trail."""

    groups: ClassVar[list] = [GROUP_ADMIN]
    paginate_by = 25

    def get(self, request):
        queryset = AuditLog.objects.select_related("user").order_by("-created_at")

        action = request.GET.get("action", "").strip()
        if action:
            queryset = queryset.filter(action=action)
        actor = request.GET.get("actor", "").strip()
        if actor:
            queryset = queryset.filter(user__email__icontains=actor)

        page = Paginator(queryset, self.paginate_by).get_page(request.GET.get("page"))
        context = {
            "page_obj": page,
            "actions": AuditAction.choices,
            "selected_action": action,
            "actor": actor,
        }
        from django.utils import timezone

        props = {
            "entries": [
                {
                    "id": e.pk,
                    "when": timezone.localtime(e.created_at).isoformat(),
                    "action": e.action,
                    "actionLabel": str(e.get_action_display()),
                    "user": e.user.email if e.user_id else "",
                    "target": f"{e.target_type}#{e.target_id}" if e.target_type else "",
                    "metadata": e.metadata or {},
                }
                for e in page.object_list
            ],
            "actions": [{"value": v, "label": str(label)} for v, label in AuditAction.choices],
            "action": action,
            "actor": actor,
            "page": page.number,
            "pages": page.paginator.num_pages,
            "total": page.paginator.count,
        }
        return inertia_render(request, "Admin/Audit", props=props, template_data=context)


class SeasonListView(GroupRequiredMixin, LoginRequiredMixin, View):
    """Admin: manage seasons — each one a closed cash box."""

    groups: ClassVar[list] = [GROUP_ADMIN]
    admin_scope: ClassVar[str] = "penalty"

    def get(self, request):
        seasons = Season.objects.annotate(
            matchday_count=Count("matchdays", distinct=True),
            payment_count=Count("payments", distinct=True),
            team_count=Count("teams", distinct=True),
        ).order_by("-name")
        context = {"seasons": seasons, "default_season": Season.default()}
        props = {
            "seasons": [
                {
                    "id": s.pk,
                    "name": s.name,
                    "isDefault": s.is_default,
                    "matchdays": s.matchday_count,
                    "payments": s.payment_count,
                    "teams": s.team_count,
                    "editUrl": reverse("season_update", args=[s.pk]),
                    "defaultUrl": reverse("season_set_default", args=[s.pk]),
                }
                for s in seasons
            ],
        }
        return inertia_render(request, "Admin/Seasons", props=props, template_data=context)


def _nuliga_table(form):
    """One nuLiga team page per team (the import of its matchdays)."""

    def status(team):
        link = form.nuliga_status.get(team.pk)
        if link is None or link.last_sync_at is None:
            return team.name
        when = timezone.localtime(link.last_sync_at).strftime("%d.%m. %H:%M")
        if link.last_error:
            return f"{team.name} · ⚠ {link.last_error}"
        return f"{team.name} · ✓ {when}"

    return {
        "title": str(_("nuLiga")),
        "help": str(
            _(
                "Paste the address of the team page in nuLiga (open the league, click the "
                "team, copy the address). The matchdays of this season are imported right "
                "away and then checked every day; the captain is told about every change."
            )
        ),
        "headers": [str(_("Team")), str(_("nuLiga team page"))],
        "rows": [
            {"label": status(team), "fields": [f"nuliga_{team.pk}"]} for team in form.nuliga_teams
        ],
        "empty": str(_("No teams yet.")),
        "wide": True,
    }


def _import_nuliga(request, form, season):
    """Save the team pages, import the new or changed ones right away and
    show the outcome as one summary dialog on the next page."""
    from app.matchdays.nuliga import NuligaError, remember_report, report, sync_link

    reports = []
    for link in form.save_nuliga(season):
        try:
            result = sync_link(link, notify=False, actor=request.user)
        except NuligaError as exc:
            reports.append(report(link, error=str(exc)))
            continue
        reports.append(report(link, result))
    remember_report(request, reports)


def _season_form_page(request, form, season=None):
    """The season create/edit form as the generic React form page."""
    props = {
        "fields": form_schema(form),
        "errors": form_errors(form) if form.is_bound else {},
        "action": request.get_full_path(),
        "title": str(_("Edit season")) if season else str(_("New season")),
        "subtitle": season.name if season else "",
        "submitLabel": str(_("Save changes")) if season else str(_("Create season")),
        "cancelUrl": reverse("season_list"),
        "table": _nuliga_table(form),
        "groups": [
            {"title": str(_("Season")), "rows": [["name"], ["is_default"]]},
            {"title": str(_("Teams")), "rows": [["teams"]]},
        ],
    }
    if season is not None:
        props.update(
            deleteUrl=reverse("season_delete", args=[season.pk]),
            deleteLabel=str(_("Delete season")),
            deleteConfirm=str(
                _("Delete this season? Only empty seasons without open amounts can be deleted.")
            ),
        )
    return inertia_render(
        request, "Common/Form", props=props, template_data={"form": form, "season": season}
    )


class SeasonCreateView(GroupRequiredMixin, LoginRequiredMixin, View):
    """GET: empty season form. POST: create a new season."""

    groups: ClassVar[list] = [GROUP_ADMIN]
    admin_scope: ClassVar[str] = "penalty"

    def get(self, request):
        return _season_form_page(request, SeasonForm())

    def post(self, request):
        form = SeasonForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                first_season = not Season.objects.exists()
                season = form.save()
                if first_season:
                    # Assignments created before the first season existed (fresh
                    # install) become that season's roster — every later season
                    # starts EMPTY and gets its assignment per season.
                    bind_unassigned_memberships(season)
                log_action(
                    AuditAction.SEASON_CREATED,
                    user=request.user,
                    target=season,
                    metadata={"name": season.name, "changes": form_changes(form)},
                )
            messages.success(request, _("Season created."))
            _import_nuliga(request, form, season)
            return redirect("season_list")
        return _season_form_page(request, form)


class SeasonUpdateView(GroupRequiredMixin, LoginRequiredMixin, View):
    """POST/GET: rename a season, pick its active teams, toggle the default."""

    groups: ClassVar[list] = [GROUP_ADMIN]
    admin_scope: ClassVar[str] = "penalty"

    def get_object(self):
        return get_object_or_404(Season, pk=self.kwargs["pk"])

    def get(self, request, pk):
        season = self.get_object()
        return _season_form_page(request, SeasonForm(instance=season), season)

    def post(self, request, pk):
        season = self.get_object()
        form = SeasonForm(request.POST, instance=season)
        if form.is_valid():
            changes = form_changes(form)
            form.save()
            log_action(
                AuditAction.SEASON_UPDATED,
                user=request.user,
                target=season,
                metadata={"name": season.name, "changes": changes},
            )
            messages.success(request, _("Season updated."))
            _import_nuliga(request, form, season)
            return redirect("season_list")
        return _season_form_page(request, form, season)


class SeasonSetDefaultView(GroupRequiredMixin, LoginRequiredMixin, View):
    """POST-only: mark one season as the GLOBAL default for every user.

    This is the only place that changes the default of all users — the navbar
    dropdown never touches it (it only stores a session-scoped view choice).
    """

    groups: ClassVar[list] = [GROUP_ADMIN]
    admin_scope: ClassVar[str] = "penalty"

    def post(self, request, pk):
        season = get_object_or_404(Season, pk=pk)
        season.is_default = True
        season.save()  # clears the flag of every other season
        log_action(
            AuditAction.SEASON_UPDATED,
            user=request.user,
            target=season,
            metadata={"default": True},
        )
        messages.success(
            request, _("Season '%(name)s' is now the default season.") % {"name": season.name}
        )
        return redirect("season_list")


class SeasonDeleteView(GroupRequiredMixin, LoginRequiredMixin, View):
    """POST-only: only truly empty seasons can go.

    Blocked when the season still holds **open amounts** (Σ penalties ≠ Σ
    payments), matchdays, payments or player-team assignments (roster
    history would be cascade-deleted otherwise).
    """

    groups: ClassVar[list] = [GROUP_ADMIN]
    admin_scope: ClassVar[str] = "penalty"

    def post(self, request, pk):
        season = get_object_or_404(Season, pk=pk)
        if season_open_balance(season) != Decimal(0):
            messages.error(
                request,
                _(
                    "This season cannot be deleted because it still has open amounts. "
                    "Settle all balances first."
                ),
            )
            return redirect("season_list")
        if season.matchdays.exists() or season.payments.exists():
            messages.error(
                request,
                _("This season cannot be deleted because it still has matchdays or payments."),
            )
            return redirect("season_list")
        if season.player_team_assignments.exists():
            messages.error(
                request,
                _("This season cannot be deleted because players are still assigned to it."),
            )
            return redirect("season_list")
        log_action(
            AuditAction.SEASON_DELETED,
            user=request.user,
            target=season,
            metadata={"name": season.name},
        )
        season.delete()
        messages.success(request, _("Season deleted."))
        return redirect("season_list")


class SeasonSetView(LoginRequiredMixin, View):
    """POST-only: pick the season shown by THIS user (session only).

    Purely personal: it never changes the admin-set default season, so other
    users keep seeing the default. The choice lasts as long as the session.
    """

    def post(self, request):
        fallback = safe_next_url(request, "/")
        # Non-numeric / empty ids are 404s, not unhandled ValueErrors (500).
        season = Season.objects.filter(pk=numeric_pk(request.POST.get("season"))).first()
        if season is None:
            messages.error(request, _("Season not found."))
            return redirect(fallback)
        set_active_season(request, season)
        return redirect(fallback)
