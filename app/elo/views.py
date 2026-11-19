"""Elo module pages (React + Mantine via Inertia; data and rights stay here).

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
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views import View
from inertia import render as inertia_render

from app.core.inertia_utils import form_errors, request_data
from app.core.permissions import user_is_elo_admin
from app.elo import notify
from app.elo.conf import elo_setting
from app.elo.forms import EloPlayerAddForm, EloPlayerEditForm, MatchEditForm, MatchForm
from app.elo.models import EloProfile, Match
from app.elo.services import h2h as h2h_service
from app.elo.services import matches as match_service
from app.elo.services import players as player_service
from app.elo.services import ranking as ranking_service
from app.elo.services.validation import VALID_BEST_OF
from app.players.avatars import avatars_for
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
        if start > end:  # an inverted range is swapped, never an error page
            start, end = end, start
        end = min(end, today)  # nothing after today
        start = min(start, end)
    else:
        start, end = today.replace(day=1), today
    return {"key": key, "from": start, "to": end}


class EloAdminMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not user_is_elo_admin(request.user):
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
        pics = avatars_for(e.player_id for e in ranking.entries)
        return inertia_render(
            request,
            "Elo/Ranking",
            props={
                "period": period_props(period),
                "includeInactive": include_inactive,
                "entries": [entry_props(e, pics) for e in ranking.entries],
                "fieldSize": ranking.field_size,
                "matchCount": Match.objects.filter(
                    date__gte=period["from"], date__lte=period["to"]
                ).count(),
                "myPlayerId": _my_player_id(request.user),
                "today": timezone.localdate().isoformat(),
            },
        )


def period_props(period) -> dict:
    return {
        "key": period["key"],
        "from": period["from"].isoformat(),
        "to": period["to"].isoformat(),
    }


def entry_props(e, pics) -> dict:
    return {
        "playerId": e.player_id,
        "name": e.name,
        "avatar": pics.get(e.player_id, ""),
        "position": e.position,
        "elo": round(e.elo, 2),
        "eloChange": round(e.elo_change, 1),
        "positionChange": e.position_change,
        "matches": e.matches,
        "wins": e.wins,
        "total180s": e.total_180s,
        "bestFinish": e.best_high_finish,
        "inactive": e.inactive,
        "disabled": e.disabled,
    }


class AllTimeView(LoginRequiredMixin, View):
    def get(self, request):
        include_inactive = request.GET.get("inactive", "1") != "0"
        rows = ranking_service.all_players_all_time_high(include_inactive)
        pics = avatars_for(r["player_id"] for r in rows)
        return inertia_render(
            request,
            "Elo/AllTime",
            props={
                "includeInactive": include_inactive,
                "rows": [
                    {
                        "playerId": r["player_id"],
                        "name": r["name"],
                        "avatar": pics.get(r["player_id"], ""),
                        "maxElo": round(r["max_elo"], 1),
                        "dateReached": r["date_reached"].isoformat() if r["date_reached"] else None,
                        "inactive": r["inactive"],
                        "disabled": r["disabled"],
                    }
                    for r in rows
                ],
            },
        )


def elo_players(include_disabled=False) -> list[dict]:
    """Players for pickers: id, name, Elo, picture, disabled."""
    qs = EloProfile.objects.select_related("player").order_by("player__name")
    if not include_disabled:
        qs = qs.filter(disabled=False)
    profiles = list(qs)
    pics = avatars_for(p.player_id for p in profiles)
    return [
        {
            "id": p.player_id,
            "name": p.player.name,
            "elo": round(p.current_elo),
            "avatar": pics.get(p.player_id, ""),
            "disabled": p.disabled,
            "entryDate": p.entry_date.isoformat(),
        }
        for p in profiles
    ]


def match_props(m, pics=None) -> dict:
    pics = pics or {}
    return {
        "id": m.pk,
        "date": m.date.isoformat(),
        "bestOf": m.best_of_legs,
        "a": {"id": m.player_a_id, "name": m.player_a.name, "avatar": pics.get(m.player_a_id, "")},
        "b": {"id": m.player_b_id, "name": m.player_b.name, "avatar": pics.get(m.player_b_id, "")},
        "scoreA": m.score_a if m.score_a is not None else 0,
        "scoreB": m.score_b if m.score_b is not None else 0,
        "winnerId": m.winner_id,
        "eloChangeA": round(m.elo_change_a, 1),
        "eloChangeB": round(m.elo_change_b, 1),
        "avgA": m.a_average,
        "avgB": m.b_average,
    }


def _limits() -> dict:
    return {
        "hfMin": elo_setting("HIGH_FINISH_MIN"),
        "hfMax": elo_setting("HIGH_FINISH_MAX"),
        "ldMin": elo_setting("LOW_DARTS_MIN"),
        "ldMax": elo_setting("LOW_DARTS_MAX"),
    }


# ---------------------------------------------------------------- matches
class MatchListView(LoginRequiredMixin, View):
    def get(self, request):
        qs = Match.objects.select_related("player_a", "player_b").order_by(
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
        rows = list(page.object_list)
        pics = avatars_for({m.player_a_id for m in rows} | {m.player_b_id for m in rows})
        return inertia_render(
            request,
            "Elo/MatchList",
            props={
                "matches": [match_props(m, pics) for m in rows],
                "page": page.number,
                "pages": page.paginator.num_pages,
                "total": page.paginator.count,
                "filters": {
                    "player": player_id if player_id and player_id.isdigit() else "",
                    "from": start.isoformat() if start else "",
                    "to": end.isoformat() if end else "",
                },
                "players": [{"id": p["id"], "name": p["name"]} for p in elo_players(True)],
                "isAdmin": user_is_elo_admin(request.user),
                "today": timezone.localdate().isoformat(),
            },
        )


class MatchCreateView(LoginRequiredMixin, View):
    def _props(self, request, form=None, duplicate=False, initial=None):
        return {
            "players": elo_players(),
            "defaults": initial or {},
            "bestOfChoices": list(VALID_BEST_OF),
            "defaultBestOf": elo_setting("BEST_OF_LEGS"),
            "today": timezone.localdate().isoformat(),
            "duplicate": duplicate,
            "errors": form_errors(form) if form is not None else {},
            "limits": _limits(),
        }

    def get(self, request):
        initial = {}
        mine = _my_player_id(request.user)
        if mine:
            initial["playerA"] = mine
        for key, name in (("a", "playerA"), ("b", "playerB")):
            if request.GET.get(key, "").isdigit():
                initial[name] = int(request.GET[key])
        return inertia_render(
            request, "Elo/MatchCreate", props=self._props(request, initial=initial)
        )

    def post(self, request):
        form = MatchForm(request_data(request))
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
                if form.data.get("again") in ("1", "true", "True", "on"):
                    return redirect(reverse("elo:match_create") + f"?a={match.player_a_id}")
                return redirect("elo:match_detail", pk=match.pk)
        initial = {
            "playerA": form.data.get("player_a"),
            "playerB": form.data.get("player_b"),
        }
        return inertia_render(
            request, "Elo/MatchCreate", props=self._props(request, form, duplicate, initial)
        )


class MatchDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        m = get_object_or_404(
            Match.objects.select_related("player_a", "player_b", "created_by"), pk=pk
        )
        pics = avatars_for([m.player_a_id, m.player_b_id])

        def side(s):
            pid = getattr(m, f"player_{s}_id")
            return {
                "id": pid,
                "name": getattr(m, f"player_{s}").name,
                "avatar": pics.get(pid, ""),
                "score": getattr(m, f"score_{s}") if getattr(m, f"score_{s}") is not None else 0,
                "won": m.winner_id == pid,
                "eloBefore": round(getattr(m, f"elo_before_{s}"), 1),
                "eloAfter": round(getattr(m, f"elo_after_{s}"), 1),
                "eloChange": round(getattr(m, f"elo_change_{s}"), 1),
                "n180": getattr(m, f"{s}_180s"),
                "hf": getattr(m, f"{s}_high_finishes") or [],
                "ld": getattr(m, f"{s}_low_darts") or [],
                "average": getattr(m, f"{s}_average"),
            }

        creator = m.created_by
        return inertia_render(
            request,
            "Elo/MatchDetail",
            props={
                "match": {
                    "id": m.pk,
                    "date": m.date.isoformat(),
                    "bestOf": m.best_of_legs,
                    "kFactor": m.k_factor,
                    "createdAt": timezone.localtime(m.created_at).strftime("%d.%m.%Y %H:%M"),
                    "createdBy": (creator.full_name or creator.email) if creator else "",
                },
                "a": side("a"),
                "b": side("b"),
                "canEdit": user_is_elo_admin(request.user),
            },
        )


class MatchUpdateView(LoginRequiredMixin, EloAdminMixin, View):
    def _props(self, m, form=None, duplicate=False):
        return {
            "match": {
                "id": m.pk,
                "a": m.player_a.name,
                "b": m.player_b.name,
                "date": m.date.isoformat(),
                "bestOf": m.best_of_legs,
                "scoreA": m.score_a or 0,
                "scoreB": m.score_b or 0,
                "stats": {k: getattr(m, k) for k in MatchEditForm.STAT_KEYS},
            },
            "bestOfChoices": list(VALID_BEST_OF),
            "today": timezone.localdate().isoformat(),
            # Earliest allowed date: both players must already be in the ranking.
            "minDate": max(
                (p.elo.entry_date for p in (m.player_a, m.player_b) if hasattr(p, "elo")),
                default=None,
            ),
            "duplicate": duplicate,
            "errors": form_errors(form) if form is not None else {},
            "limits": _limits(),
        }

    def get(self, request, pk):
        m = get_object_or_404(Match.objects.select_related("player_a", "player_b"), pk=pk)
        return inertia_render(request, "Elo/MatchEdit", props=self._props(m))

    def post(self, request, pk):
        m = get_object_or_404(Match.objects.select_related("player_a", "player_b"), pk=pk)
        form = MatchEditForm(request_data(request), match=m)
        duplicate = False
        if form.is_valid():
            d = form.cleaned_data
            try:
                m = match_service.update_match(
                    m,
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
                notify.match_changed(m, actor=request.user, action="updated", request=request)
                messages.success(request, _("Match updated - the ranking was recalculated."))
                return redirect("elo:match_detail", pk=m.pk)
        return inertia_render(request, "Elo/MatchEdit", props=self._props(m, form, duplicate))


class MatchDeleteView(LoginRequiredMixin, EloAdminMixin, View):
    """POST only - the confirmation is a dialog on the match page."""

    def get(self, request, pk):
        return redirect("elo:match_detail", pk=pk)

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
        opponents = h2h_service.opponents(pk)
        pics = avatars_for({pk} | {o["player_id"] for o in opponents})
        ath = ranking_service.all_time_high_elo(profile)
        best = ranking_service.best_rank(pk)
        return inertia_render(
            request,
            "Elo/PlayerDetail",
            props={
                "player": {
                    "id": pk,
                    "name": profile.player.name,
                    "avatar": pics.get(pk, ""),
                    "elo": round(profile.current_elo, 1),
                    "entryDate": profile.entry_date.isoformat(),
                    "disabled": profile.disabled,
                },
                "rank": positions.get(pk),
                "fieldSize": len(positions),
                "ath": {
                    "elo": round(ath["max_elo"], 1),
                    "date": ath["date_reached"].isoformat() if ath["date_reached"] else None,
                },
                "best": {
                    "rank": best["best_rank"],
                    "date": best["date_reached"].isoformat() if best["date_reached"] else None,
                },
                "period": period_props(period),
                "today": timezone.localdate().isoformat(),
                "stats": stats,
                "eloHistory": ranking_service.elo_history(pk),
                "avgHistory": ranking_service.average_history(pk),
                "opponents": [
                    {
                        "id": o["player_id"],
                        "name": o["name"],
                        "wins": o["wins"],
                        "losses": o["losses"],
                        "matches": o["matches"],
                    }
                    for o in opponents
                ],
                "recent": [
                    {
                        "id": m.pk,
                        "date": m.date.isoformat(),
                        "won": m.winner_id == pk,
                        "me": m.legs(pk) or 0,
                        "opp": (m.score_b if m.player_a_id == pk else m.score_a) or 0,
                        "oppName": (m.player_b if m.player_a_id == pk else m.player_a).name,
                        "change": round(m.elo_change(pk), 1),
                    }
                    for m in recent
                ],
                "canEdit": user_is_elo_admin(request.user),
            },
        )


class HeadToHeadView(LoginRequiredMixin, View):
    def get(self, request):
        a = request.GET.get("a")
        b = request.GET.get("b")
        props = {
            "players": elo_players(True),
            "aId": None,
            "bId": None,
            "opponents": [],
            "h2h": None,
        }
        if a and a.isdigit():
            props["aId"] = int(a)
            props["opponents"] = [
                {"id": o["player_id"], "name": o["name"], "matches": o["matches"]}
                for o in h2h_service.opponents(int(a))
            ]
        if a and b and a.isdigit() and b.isdigit():
            props["bId"] = int(b)
            try:
                res = h2h_service.head_to_head(int(a), int(b))
            except ValidationError as exc:
                messages.error(request, " ".join(_errors(exc)))
            else:
                pics = avatars_for([int(a), int(b)])
                for key in ("a", "b"):
                    res[key]["avatar"] = pics.get(res[key]["player_id"], "")
                res["recent"] = [
                    {
                        "id": r["match"].pk,
                        "date": r["date"].isoformat(),
                        "winnerId": r["winner_id"],
                        "scoreA": r["score_a"] or 0,
                        "scoreB": r["score_b"] or 0,
                        "eloChangeA": round(r["elo_change_a"], 1),
                        "avgA": r["average_a"],
                        "avgB": r["average_b"],
                    }
                    for r in res["recent"]
                ]
                for key in ("first_meeting", "last_meeting"):
                    res[key] = res[key].isoformat() if res[key] else None
                props["h2h"] = res
        return inertia_render(request, "Elo/HeadToHead", props=props)


# ---------------------------------------------------------------- admin
class ManageView(LoginRequiredMixin, EloAdminMixin, View):
    def get(self, request):
        return inertia_render(
            request,
            "Elo/Manage",
            props={
                "players": [
                    {**p, "startElo": EloProfile.objects.get(player_id=p["id"]).start_elo}
                    for p in elo_players(True)
                ],
                "matchTotal": Match.objects.count(),
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
    def _props(self, form=None):
        return {
            "mode": "add",
            "persons": [
                {"id": p.pk, "name": p.name}
                for p in Player.objects.filter(elo__isnull=True).order_by("name")
            ],
            "defaults": {
                "startElo": elo_setting("DEFAULT_ELO"),
                "entryDate": timezone.localdate().isoformat(),
            },
            "today": timezone.localdate().isoformat(),
            "errors": form_errors(form) if form is not None else {},
        }

    def get(self, request):
        return inertia_render(request, "Elo/PlayerForm", props=self._props())

    def post(self, request):
        form = EloPlayerAddForm(request_data(request))
        if form.is_valid():
            d = form.cleaned_data
            try:
                profile = player_service.add_to_ranking(
                    player=d["existing"], name=d["name"], start_elo=d["start_elo"],
                    entry_date=d["entry_date"], user=request.user,
                )  # fmt: skip
            except ValidationError as exc:
                for msg in _errors(exc):
                    form.add_error(None, msg)
            else:
                messages.success(
                    request, _("%(name)s is now in the Elo ranking.") % {"name": profile.name}
                )
                return redirect("elo:manage")
        return inertia_render(request, "Elo/PlayerForm", props=self._props(form))


class PlayerEditView(LoginRequiredMixin, EloAdminMixin, View):
    def _props(self, profile, form=None):
        first = player_service.first_match_date(profile.player_id)
        return {
            "mode": "edit",
            "player": {
                "id": profile.player_id,
                "name": profile.player.name,
                "avatar": avatars_for([profile.player_id]).get(profile.player_id, ""),
                "startElo": profile.start_elo,
                "entryDate": profile.entry_date.isoformat(),
                "firstMatch": first.isoformat() if first else None,
            },
            "today": timezone.localdate().isoformat(),
            "errors": form_errors(form) if form is not None else {},
        }

    def get(self, request, pk):
        profile = get_object_or_404(EloProfile.objects.select_related("player"), player_id=pk)
        return inertia_render(request, "Elo/PlayerForm", props=self._props(profile))

    def post(self, request, pk):
        profile = get_object_or_404(EloProfile.objects.select_related("player"), player_id=pk)
        form = EloPlayerEditForm(request_data(request), profile=profile)
        if form.is_valid():
            d = form.cleaned_data
            try:
                player_service.update_profile(
                    profile, name=d["name"], start_elo=d["start_elo"],
                    entry_date=d["entry_date"], user=request.user,
                )  # fmt: skip
            except ValidationError as exc:
                for msg in _errors(exc):
                    form.add_error(None, msg)
            else:
                messages.success(request, _("Player saved."))
                return redirect("elo:manage")
        return inertia_render(request, "Elo/PlayerForm", props=self._props(profile, form))


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


def chart_json(data) -> str:
    return json.dumps(data)
