""" "My overview": one card per module the user may use (Elo + penalty)."""

from django.utils import timezone

from app.core.access import user_modules


def _elo_card(user) -> dict:
    from app.elo.models import EloProfile
    from app.elo.services import ranking as ranking_service

    today = timezone.localdate()
    month = ranking_service.generate_ranking(today.replace(day=1), today, include_inactive=True)
    card = {"top": [e for e in month.entries][:3], "field_size": month.field_size, "me": None}
    pid = getattr(user, "player_link_id", None)
    profile = (
        EloProfile.objects.filter(player_id=pid).select_related("player").first() if pid else None
    )
    if profile is not None:
        entry = next((e for e in month.entries if e.player_id == pid), None)
        recent = list(
            ranking_service.player_matches(pid).order_by("-date", "-created_at", "-id")[:3]
        )
        for m in recent:
            m.me_won = m.winner_id == pid
            m.opp = m.player_b if m.player_a_id == pid else m.player_a
            m.me_score, m.opp_score = m.legs(pid), m.legs(m.opp.pk)
        card["me"] = {"profile": profile, "entry": entry, "recent": recent}
    return card


def _penalty_card(user, request=None) -> dict:
    from app.matchdays.models import Season
    from app.penalties.services import player_balance, player_total, player_total_paid

    player = getattr(user, "player_link", None)
    if player is None:
        return {"me": None}
    season = (
        Season.objects.filter(is_default=True).first() or Season.objects.order_by("-name").first()
    )
    return {
        "me": player,
        "season": season,
        "total": player_total(player, season=season),
        "paid": player_total_paid(player, season=season),
        "balance": player_balance(player, season=season),
    }


def build_overview(user) -> dict:
    mods = user_modules(user)
    ctx = {"modules_for_user": mods, "nav_section": "overview"}
    if mods.get("elo"):
        ctx["elo"] = _elo_card(user)
    if mods.get("penalty"):
        ctx["penalty"] = _penalty_card(user)
    return ctx
