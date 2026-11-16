"""Elo module pages (server-rendered, phone first).

Read pages and match entry: every account with Elo access.
Editing/deleting matches, managing Elo players, recalculation and exports:
Admins only (captains are NOT Elo admins).
"""

import csv
import json
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views import View

from app.core.permissions import user_is_admin
from app.elo import notify
from app.elo.forms import EloPlayerAddForm, EloPlayerEditForm, MatchEditForm, MatchForm
from app.elo.models import EloProfile, Match
from app.elo.services import h2h as h2h_service
from app.elo.services import matches as match_service
from app.elo.services import players as player_service
from app.elo.services import ranking as ranking_service
from app.players.models import Player

PERIODS = ("month", "last_month", "year", "all", "custom")


def resolve_period(request) -> dict:
    """Period chips: this month (default), last month, this year, all time, custom."""
    today = timezone.localdate()
    key = request.GET.get("period") or "month"
    if key not in PERIODS:
        key = "month"
    if key == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
    elif key == "year":
        start, end = date(today.year, 1, 1), today
    elif key == "all":
        first = Match.objects.order_by("date").values_list("date", flat=True).first()
        start, end = (first or today), today
    elif key == "custom":
        start = parse_date(request.GET.get("from") or "") or today.replace(day=1)
        end = parse_date(request.GET.get("to") or "") or today
    else:
        start, end = today.replace(day=1), today
    return {"key": key, "from": start, "to": end}


class EloAdminMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not user_is_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def _errors(exc: ValidationError) -> list[str]:
    return [str(m) for m in exc.messages]


def _my_player_id(user):
    pid = getattr(user, "player_link_id", None)
    if pid and EloProfile.objects.filter(player_id=pid).exists():
        return pid
    return None


# ---------------------------------------------------------------- ranking
class RankingView(LoginRequiredMixin, View):
    def get(self, request):
        period = resolve_period(request)
        include_inactive = request.GET.get("inactive", "1") != "0"
        try:
            ranking = ranking_service.generate_ranking(
                period["from"], period["to"], include_inactive=include_inactive
            )
        except ValidationError as exc:
            messages.error(request, " ".join(_errors(exc)))
            return redirect("elo:ranking")
        entries = ranking.entries
        return render(
            request,
            "elo/ranking.html",
            {
                "period": period,
                "include_inactive": include_inactive,
                "entries": entries,
                "podium": entries[:3] if len(entries) >= 3 else [],
                "field_size": ranking.field_size,
                "my_player_id": _my_player_id(request.user),
                "match_count": Match.objects.filter(
                    date__gte=period["from"], date__lte=period["to"]
                ).count(),
                "nav_section": "elo",
            },
        )


class AllTimeView(LoginRequiredMixin, View):
    def get(self, request):
        include_inactive = request.GET.get("inactive", "1") != "0"
        rows = ranking_service.all_players_all_time_high(include_inactive)
        return render(
            request,
            "elo/all_time.html",
            {"rows": rows, "include_inactive": include_inactive, "nav_section": "elo"},
        )


# ---------------------------------------------------------------- matches
class MatchListView(LoginRequiredMixin, View):
    def get(self, request):
        qs = Match.objects.select_related("player_a", "player_b", "winner").order_by(
            "-date", "-created_at", "-id"
        )
        player_id = request.GET.get("player")
        start = parse_date(request.GET.get("from") or "")
        end = parse_date(request.GET.get("to") or "")
        if player_id and player_id.isdigit():
            qs = qs.filter(Q(player_a_id=player_id) | Q(player_b_id=player_id))
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        page = Paginator(qs, 25).get_page(request.GET.get("page"))
        query = request.GET.copy()
        query.pop("page", None)
        return render(
            request,
            "elo/match_list.html",
            {
                "page": page,
                "players": Player.objects.filter(elo__isnull=False).order_by("name"),
                "selected_player": int(player_id) if player_id and player_id.isdigit() else None,
                "date_from": start,
                "date_to": end,
                "query": query.urlencode(),
                "is_admin": user_is_admin(request.user),
                "nav_section": "elo",
            },
        )


class MatchCreateView(LoginRequiredMixin, View):
    template_name = "elo/match_form.html"

    def get(self, request):
        initial = {}
        mine = _my_player_id(request.user)
        if mine:
            initial["player_a"] = mine
        if request.GET.get("a", "").isdigit():
            initial["player_a"] = int(request.GET["a"])
        if request.GET.get("b", "").isdigit():
            initial["player_b"] = int(request.GET["b"])
        return render(request, self.template_name, self._ctx(MatchForm(initial=initial)))

    def post(self, request):
        form = MatchForm(request.POST)
        duplicate = False
        if form.is_valid():
            d = form.cleaned_data
            try:
                match = match_service.create_match(
                    player_a=d["player_a"],
                    player_b=d["player_b"],
                    match_date=d["match_date"],
                    score_a=d["score_a"],
                    score_b=d["score_b"],
                    best_of_legs=d["best_of_legs"],
                    stats=form.stats(),
                    user=request.user,
                    force=d.get("force", False),
                )
            except match_service.DuplicateMatchError:
                duplicate = True
            except ValidationError as exc:
                for msg in _errors(exc):
                    form.add_error(None, msg)
            else:
                notify.match_changed(match, actor=request.user, action="created", request=request)
                messages.success(
                    request,
                    _("Match saved: %(a)s %(sa)s:%(sb)s %(b)s")
                    % {
                        "a": match.player_a.name,
                        "sa": match.score_a,
                        "sb": match.score_b,
                        "b": match.player_b.name,
                    },
                )
                if request.POST.get("again"):
                    return redirect(reverse("elo:match_create") + f"?a={match.player_a_id}")
                return redirect("elo:match_detail", pk=match.pk)
        return render(request, self.template_name, self._ctx(form, duplicate=duplicate))

    def _ctx(self, form, duplicate=False):
        profiles = {
            p.player_id: {"elo": round(p.current_elo), "name": p.player.name}
            for p in EloProfile.objects.select_related("player").filter(disabled=False)
        }
        return {
            "form": form,
            "duplicate": duplicate,
            "players_json": profiles,
            "nav_section": "elo",
        }


class MatchDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        match = get_object_or_404(
            Match.objects.select_related("player_a", "player_b", "created_by"), pk=pk
        )
        sides = []
        for side in ("a", "b"):
            pid = getattr(match, f"player_{side}_id")
            sides.append(
                {
                    "player": getattr(match, f"player_{side}"),
                    "score": getattr(match, f"score_{side}"),
                    "won": match.winner_id == pid,
                    "elo_before": getattr(match, f"elo_before_{side}"),
                    "elo_after": getattr(match, f"elo_after_{side}"),
                    "elo_change": getattr(match, f"elo_change_{side}"),
                    "n180": getattr(match, f"{side}_180s"),
                    "hf": getattr(match, f"{side}_high_finishes") or [],
                    "ld": getattr(match, f"{side}_low_darts") or [],
                    "average": getattr(match, f"{side}_average"),
                }
            )
        return render(
            request,
            "elo/match_detail.html",
            {
                "match": match,
                "a": sides[0],
                "b": sides[1],
                "is_admin": user_is_admin(request.user),
                "nav_section": "elo",
            },
        )


class MatchUpdateView(LoginRequiredMixin, EloAdminMixin, View):
    template_name = "elo/match_edit.html"

    def get(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        return render(
            request,
            self.template_name,
            {"form": MatchEditForm(match=match), "match": match, "nav_section": "elo"},
        )

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        form = MatchEditForm(request.POST, match=match)
        duplicate = False
        if form.is_valid():
            d = form.cleaned_data
            try:
                match = match_service.update_match(
                    match,
                    user=request.user,
                    force=d.get("force", False),
                    match_date=d["match_date"],
                    best_of_legs=d["best_of_legs"],
                    score_a=d["score_a"],
                    score_b=d["score_b"],
                    **form.stats(),
                )
            except match_service.DuplicateMatchError:
                duplicate = True
            except ValidationError as exc:
                for msg in _errors(exc):
                    form.add_error(None, msg)
            else:
                notify.match_changed(match, actor=request.user, action="updated", request=request)
                messages.success(request, _("Match updated - the ranking was recalculated."))
                return redirect("elo:match_detail", pk=match.pk)
        return render(
            request,
            self.template_name,
            {"form": form, "match": match, "duplicate": duplicate, "nav_section": "elo"},
        )


class MatchDeleteView(LoginRequiredMixin, EloAdminMixin, View):
    def get(self, request, pk):
        match = get_object_or_404(Match.objects.select_related("player_a", "player_b"), pk=pk)
        return render(request, "elo/match_delete.html", {"match": match, "nav_section": "elo"})

    def post(self, request, pk):
        match = get_object_or_404(Match.objects.select_related("player_a", "player_b"), pk=pk)
        notify.match_changed(match, actor=request.user, action="deleted", request=request)
        match_service.delete_match(match, user=request.user)
        messages.success(request, _("Match deleted - the ranking was recalculated."))
        return redirect("elo:match_list")


# ---------------------------------------------------------------- players
class PlayerDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        profile = get_object_or_404(EloProfile.objects.select_related("player"), player_id=pk)
        period = resolve_period(request)
        try:
            stats = ranking_service.player_statistics(pk, period["from"], period["to"])
        except ValidationError as exc:
            messages.error(request, " ".join(_errors(exc)))
            return redirect("elo:player_detail", pk=pk)
        positions = ranking_service.current_positions()
        recent = list(
            ranking_service.player_matches(pk).order_by("-date", "-created_at", "-id")[:10]
        )
        for m in recent:
            m.me_won = m.winner_id == pk
            m.me_score = m.legs(pk)
            m.opp = m.player_b if m.player_a_id == pk else m.player_a
            m.opp_score = m.score_b if m.player_a_id == pk else m.score_a
            m.me_change = m.elo_change(pk)
        return render(
            request,
            "elo/player_detail.html",
            {
                "profile": profile,
                "player": profile.player,
                "period": period,
                "stats": stats,
                "rank": positions.get(pk),
                "field_size": len(positions),
                "ath": ranking_service.all_time_high_elo(profile),
                "best": ranking_service.best_rank(pk),
                "opponents": h2h_service.opponents(pk),
                "recent": recent,
                "elo_history": ranking_service.elo_history(pk),
                "avg_history": ranking_service.average_history(pk),
                "is_admin": user_is_admin(request.user),
                "nav_section": "elo",
            },
        )


class HeadToHeadView(LoginRequiredMixin, View):
    def get(self, request):
        profiles = list(EloProfile.objects.select_related("player").order_by("player__name"))
        a = request.GET.get("a")
        b = request.GET.get("b")
        ctx = {"profiles": profiles, "a_id": None, "b_id": None, "nav_section": "elo"}
        if a and a.isdigit():
            ctx["a_id"] = int(a)
            ctx["opponents"] = h2h_service.opponents(int(a))
        if a and b and a.isdigit() and b.isdigit():
            ctx["b_id"] = int(b)
            try:
                ctx["h2h"] = h2h_service.head_to_head(int(a), int(b))
            except ValidationError as exc:
                messages.error(request, " ".join(_errors(exc)))
        return render(request, "elo/h2h.html", ctx)


# ---------------------------------------------------------------- admin
class ManageView(LoginRequiredMixin, EloAdminMixin, View):
    def get(self, request):
        profiles = list(EloProfile.objects.select_related("player").order_by("player__name"))
        return render(
            request,
            "elo/manage.html",
            {
                "profiles": profiles,
                "match_total": Match.objects.count(),
                "nav_section": "elo_admin",
            },
        )


class RecalculateView(LoginRequiredMixin, EloAdminMixin, View):
    def post(self, request):
        res = match_service.recalculate_all(user=request.user)
        messages.success(
            request,
            _("Recalculated %(m)s matches of %(p)s players.")
            % {"m": res["matches_recalculated"], "p": res["players_affected"]},
        )
        return redirect("elo:manage")


class PlayerAddView(LoginRequiredMixin, EloAdminMixin, View):
    def get(self, request):
        return render(
            request,
            "elo/player_form.html",
            {"form": EloPlayerAddForm(), "nav_section": "elo_admin"},
        )

    def post(self, request):
        form = EloPlayerAddForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                profile = player_service.add_to_ranking(
                    player=d["existing"],
                    name=d["name"],
                    start_elo=d["start_elo"],
                    entry_date=d["entry_date"],
                    user=request.user,
                )
            except ValidationError as exc:
                for msg in _errors(exc):
                    form.add_error(None, msg)
            else:
                messages.success(
                    request, _("%(name)s is now in the Elo ranking.") % {"name": profile.name}
                )
                return redirect("elo:manage")
        return render(request, "elo/player_form.html", {"form": form, "nav_section": "elo_admin"})


class PlayerEditView(LoginRequiredMixin, EloAdminMixin, View):
    def get(self, request, pk):
        profile = get_object_or_404(EloProfile.objects.select_related("player"), player_id=pk)
        return render(
            request,
            "elo/player_form.html",
            {
                "form": EloPlayerEditForm(profile=profile),
                "profile": profile,
                "nav_section": "elo_admin",
            },
        )

    def post(self, request, pk):
        profile = get_object_or_404(EloProfile.objects.select_related("player"), player_id=pk)
        form = EloPlayerEditForm(request.POST, profile=profile)
        if form.is_valid():
            d = form.cleaned_data
            try:
                player_service.update_profile(
                    profile,
                    name=d["name"],
                    start_elo=d["start_elo"],
                    entry_date=d["entry_date"],
                    user=request.user,
                )
            except ValidationError as exc:
                for msg in _errors(exc):
                    form.add_error(None, msg)
            else:
                messages.success(request, _("Player saved."))
                return redirect("elo:manage")
        return render(
            request,
            "elo/player_form.html",
            {"form": form, "profile": profile, "nav_section": "elo_admin"},
        )


class PlayerToggleView(LoginRequiredMixin, EloAdminMixin, View):
    def post(self, request, pk):
        profile = get_object_or_404(EloProfile.objects.select_related("player"), player_id=pk)
        if profile.disabled:
            player_service.reactivate(profile, user=request.user)
            messages.success(request, _("%(name)s can play again.") % {"name": profile.name})
        else:
            player_service.disable(profile, user=request.user)
            messages.success(
                request,
                _("%(name)s is disabled: stays in the ranking, cannot play new matches.")
                % {"name": profile.name},
            )
        return redirect("elo:manage")


# ---------------------------------------------------------------- exports
def _csv_response(filename: str) -> tuple[HttpResponse, csv.writer]:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")  # Excel: UTF-8 BOM
    return response, csv.writer(response, delimiter=";")


def _num(value, digits=1):
    return "" if value is None else f"{value:.{digits}f}".replace(".", ",")


class ExportMatchesCsvView(LoginRequiredMixin, EloAdminMixin, View):
    def get(self, request):
        response, w = _csv_response("elo-matches.csv")
        w.writerow(
            [
                "id", "date", "player_a", "player_b", "legs_a", "legs_b", "best_of", "winner",
                "elo_before_a", "elo_after_a", "elo_before_b", "elo_after_b",
                "180s_a", "180s_b", "high_finishes_a", "high_finishes_b",
                "low_darts_a", "low_darts_b", "average_a", "average_b",
            ]
        )  # fmt: skip
        for m in Match.objects.select_related("player_a", "player_b", "winner").order_by(
            "date", "created_at", "id"
        ):
            w.writerow(
                [
                    m.id, m.date.isoformat(), m.player_a.name, m.player_b.name, m.score_a,
                    m.score_b, m.best_of_legs, m.winner.name, _num(m.elo_before_a),
                    _num(m.elo_after_a), _num(m.elo_before_b), _num(m.elo_after_b),
                    m.a_180s, m.b_180s, " ".join(map(str, m.a_high_finishes or [])),
                    " ".join(map(str, m.b_high_finishes or [])),
                    " ".join(map(str, m.a_low_darts or [])),
                    " ".join(map(str, m.b_low_darts or [])),
                    _num(m.a_average, 2), _num(m.b_average, 2),
                ]
            )  # fmt: skip
        return response


class ExportPlayersCsvView(LoginRequiredMixin, EloAdminMixin, View):
    def get(self, request):
        response, w = _csv_response("elo-players.csv")
        w.writerow(
            ["id", "name", "start_elo", "current_elo", "entry_date", "last_match", "disabled"]
        )
        for p in EloProfile.objects.select_related("player").order_by("player__name"):
            w.writerow(
                [
                    p.player_id,
                    p.player.name,
                    p.start_elo,
                    _num(p.current_elo),
                    p.entry_date.isoformat(),
                    p.last_match_date.isoformat() if p.last_match_date else "",
                    "yes" if p.disabled else "no",
                ]
            )
        return response


class ExportRankingCsvView(LoginRequiredMixin, EloAdminMixin, View):
    def get(self, request):
        period = resolve_period(request)
        ranking = ranking_service.generate_ranking(
            period["from"], period["to"], include_inactive=request.GET.get("inactive", "1") != "0"
        )
        response, w = _csv_response(f"elo-ranking-{period['from']}-{period['to']}.csv")
        w.writerow(["position", "name", "elo", "change", "matches", "wins", "180s", "best_finish"])
        for e in ranking.entries:
            w.writerow(
                [
                    e.position,
                    e.name,
                    _num(e.elo),
                    _num(e.elo_change),
                    e.matches,
                    e.wins,
                    e.total_180s,
                    e.best_high_finish or "",
                ]
            )
        return response


class ExportRankingPdfView(LoginRequiredMixin, EloAdminMixin, View):
    def get(self, request):
        from app.elo.pdf import ranking_pdf

        period = resolve_period(request)
        ranking = ranking_service.generate_ranking(
            period["from"], period["to"], include_inactive=request.GET.get("inactive", "1") != "0"
        )
        response = HttpResponse(ranking_pdf(ranking), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="elo-ranking-{period["from"]}-{period["to"]}.pdf"'
        )
        return response


def chart_json(data) -> str:
    return json.dumps(data)
