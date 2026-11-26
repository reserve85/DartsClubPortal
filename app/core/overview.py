""" "My overview": one card per module the user may use (Elo + penalty)."""

from django.utils import timezone

from app.core.access import user_modules


def _elo_card(user) -> dict:
    from app.elo.models import EloProfile
    from app.elo.services import ranking as ranking_service
    from app.players.avatars import avatars_for

    today = timezone.localdate()
    month = ranking_service.generate_ranking(today.replace(day=1), today, include_inactive=True)
    top = month.entries[:3]
    pics = avatars_for(e.player_id for e in top)
    card = {
        "top": [
            {
                "playerId": e.player_id,
                "name": e.name,
                "avatar": pics.get(e.player_id, ""),
                "position": e.position,
                "elo": round(e.elo, 1),
                "eloChange": round(e.elo_change, 1),
            }
            for e in top
        ],
        "me": None,
    }
    pid = getattr(user, "player_link_id", None)
    profile = EloProfile.objects.filter(player_id=pid).first() if pid else None
    if profile is not None:
        entry = next((e for e in month.entries if e.player_id == pid), None)
        recent = list(
            ranking_service.player_matches(pid).order_by("-date", "-created_at", "-id")[:3]
        )
        card["me"] = {
            "playerId": pid,
            "elo": round(profile.current_elo, 1),
            "position": entry.position if entry else None,
            "monthChange": round(entry.elo_change, 1) if entry else 0,
            "recent": [
                {
                    "id": m.pk,
                    "date": m.date.isoformat(),
                    "won": m.winner_id == pid,
                    "oppName": (m.player_b if m.player_a_id == pid else m.player_a).name,
                    "me": m.legs(pid) or 0,
                    "opp": (m.score_b if m.player_a_id == pid else m.score_a) or 0,
                }
                for m in recent
            ],
        }
    return card


def _penalty_card(user) -> dict:
    from app.matchdays.models import Season
    from app.penalties.services import player_balance, player_total, player_total_paid

    player = getattr(user, "player_link", None)
    if player is None:
        return {"me": None}
    season = (
        Season.objects.filter(is_default=True).first() or Season.objects.order_by("-name").first()
    )
    return {
        "me": True,
        "season": season.name if season else "",
        "total": float(player_total(player, season=season)),
        "paid": float(player_total_paid(player, season=season)),
        "balance": float(player_balance(player, season=season)),
    }


NEXT_DAYS = 14


def _next_matchdays(user) -> list:
    """Per team of the season: every matchday of the next two weeks, at
    least the next one. The account's own teams come first."""
    from datetime import timedelta

    from app.core.permissions import user_can_manage_team
    from app.matchdays.models import Matchday, Season
    from app.players.models import PlayerTeam
    from app.teams.services import teams_for_season

    season = (
        Season.objects.filter(is_default=True).first() or Season.objects.order_by("-name").first()
    )
    if season is None:
        return []
    today = timezone.localdate()
    own = {user.team_id} if user.team_id else set()
    player = getattr(user, "player_link", None)
    if player is not None:
        own |= set(
            PlayerTeam.objects.filter(player=player, season=season).values_list(
                "team_id", flat=True
            )
        )
    upcoming = (
        Matchday.objects.filter(season=season, date__gte=today, nuliga_removed=False)
        .select_related("team")
        .order_by("date", "start_time", "pk")
    )
    by_team: dict[int, list] = {}
    for matchday in upcoming:
        by_team.setdefault(matchday.team_id, []).append(matchday)
    rows = []
    for team in teams_for_season(season).order_by("name"):
        dates = by_team.get(team.pk, [])
        soon = [m for m in dates if m.date <= today + timedelta(days=NEXT_DAYS)]
        shown = soon or dates[:1]
        if not shown:
            continue
        can_open = user_can_manage_team(user, team)
        rows.append(
            {
                "team": team.name,
                "own": team.pk in own,
                "matchdays": [
                    {
                        "id": m.pk,
                        "date": m.date.isoformat(),
                        "time": m.start_time.strftime("%H:%M") if m.start_time else "",
                        "opponent": m.opponent,
                        "venue": m.get_venue_display(),
                        "home": m.venue == "home",
                        "location": m.location,
                        "url": f"/matchdays/{m.pk}/" if can_open else None,
                    }
                    for m in shown
                ],
            }
        )
    rows.sort(key=lambda r: (not r["own"], r["matchdays"][0]["date"], r["team"]))
    return rows


def _calendars(request, user) -> list:
    from app.matchdays.calendar import calendar_links
    from app.matchdays.models import Season
    from app.players.models import PlayerTeam
    from app.teams.services import teams_for_season

    season = (
        Season.objects.filter(is_default=True).first() or Season.objects.order_by("-name").first()
    )
    own = {user.team_id} if user.team_id else set()
    player = getattr(user, "player_link", None)
    if player is not None and season is not None:
        own |= set(
            PlayerTeam.objects.filter(player=player, season=season).values_list(
                "team_id", flat=True
            )
        )
    return calendar_links(request, teams_for_season(season).order_by("name"), own)


def build_overview(user, request=None) -> dict:
    mods = user_modules(user)
    return {
        "calendars": _calendars(request, user) if mods.get("penalty") else [],
        "elo": _elo_card(user) if mods.get("elo") else None,
        "penalty": _penalty_card(user) if mods.get("penalty") else None,
        "nextMatchdays": _next_matchdays(user) if mods.get("penalty") else [],
        "today": timezone.localdate().isoformat(),
    }
