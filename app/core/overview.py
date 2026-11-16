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


def build_overview(user) -> dict:
    mods = user_modules(user)
    return {
        "elo": _elo_card(user) if mods.get("elo") else None,
        "penalty": _penalty_card(user) if mods.get("penalty") else None,
        "today": timezone.localdate().isoformat(),
    }
