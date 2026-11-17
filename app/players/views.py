"""Player views — admin manages all teams, captains only their own team."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView

from app.core.models import AuditAction
from app.core.permissions import (
    assert_admin_or_captain,
    user_can_edit_player,
    user_can_view_player,
)
from app.core.services import log_action
from app.matchdays.services import season_for_request
from app.penalties.services import (
    assigned_penalties_qs,
    player_balance,
    player_team_balance,
    player_team_paid,
    player_team_total,
    player_total,
    player_total_paid,
)
from app.players.models import Player
from app.players.services import teams_for


class PlayerDetailView(LoginRequiredMixin, DetailView):
    """Read-only player page: teams with per-team balances + penalty history."""

    model = Player
    context_object_name = "player"

    def get(self, request, *args, **kwargs):
        # Balances and penalties only for accounts with the penalty module
        # (installed and allowed); otherwise the player's page is the Elo profile.
        from app.core.access import has_module
        from app.core.modules import ELO, PENALTY

        if not has_module(request.user, PENALTY):
            from app.elo.models import EloProfile

            pk = kwargs["pk"]
            if has_module(request.user, ELO) and EloProfile.objects.filter(player_id=pk).exists():
                return redirect("elo:player_detail", pk=pk)
            player = get_object_or_404(Player, pk=pk)
            if user_can_edit_player(request.user, player):
                return redirect("players:player_update", pk=pk)  # the member page
            raise Http404
        return super().get(request, *args, **kwargs)

    def get_object(self, queryset=None):
        player = super().get_object(queryset)
        # READ is open to every signed-in account (see user_can_view_player);
        # LoginRequiredMixin has already excluded anonymous visitors.
        if not user_can_view_player(self.request.user, player):
            raise PermissionDenied
        return player

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        player = self.object
        season = season_for_request(self.request)
        context["can_edit"] = user_can_edit_player(self.request.user, player)
        context["balance"] = player_balance(player, season=season)
        context["total"] = player_total(player, season=season)
        context["paid"] = player_total_paid(player, season=season)
        context["team_rows"] = [
            {
                "team": team,
                "total": player_team_total(player, team, season=season),
                "balance": player_team_balance(player, team, season=season),
                "paid": player_team_paid(player, team, season=season),
            }
            # Season-dependent assignment: only the active season's teams.
            for team in teams_for(player, season)
        ]
        context["penalties"] = assigned_penalties_qs(season=season).filter(player=player)[:50]
        return context

    def render_to_response(self, context, **response_kwargs):
        from django.utils import timezone
        from inertia import render as inertia_render

        from app.players.avatars import avatar_url

        player = self.object
        season = season_for_request(self.request)
        props = {
            "player": {
                "id": player.pk,
                "name": player.name,
                "active": player.active,
                "avatar": avatar_url(player),
            },
            "season": season.name if season else "",
            "canEdit": context["can_edit"],
            "totals": {
                "total": float(context["total"]),
                "paid": float(context["paid"]),
                "balance": float(context["balance"]),
            },
            "teams": [
                {
                    "id": row["team"].pk,
                    "name": row["team"].name,
                    "total": float(row["total"]),
                    "paid": float(row["paid"]),
                    "balance": float(row["balance"]),
                    "financeUrl": (
                        f"{reverse('dashboard:financial_overview')}?team={row['team'].pk}"
                    ),
                }
                for row in context["team_rows"]
            ],
            "penalties": [
                {
                    "id": pen.pk,
                    "when": timezone.localtime(pen.created_at).isoformat(),
                    "matchday": pen.matchday.display_label,
                    "matchdayId": pen.matchday_id,
                    "description": pen.display_description,
                    "amount": float(pen.amount_eur),
                }
                for pen in context["penalties"]
            ],
        }
        return inertia_render(
            self.request, "Penalty/PlayerDetail", props=props, template_data=context
        )


class PlayerDeactivateView(LoginRequiredMixin, View):
    """No hard delete — deactivation only. Keeps history and penalties."""

    def post(self, request, pk):
        assert_admin_or_captain(request.user)
        player = get_object_or_404(Player, pk=pk)
        if not user_can_edit_player(request.user, player):
            raise PermissionDenied
        player.active = False
        player.save(update_fields=["active"])
        log_action(AuditAction.PLAYER_DEACTIVATED, user=request.user, target=player)
        messages.success(request, _("Player '%(name)s' deactivated.") % {"name": player.name})
        return redirect("teams:team_list")
