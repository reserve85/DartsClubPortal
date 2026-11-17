"""Fill an EMPTY portal with realistic demo data (both modules).

    python manage.py seed_demo [--years 3] [--matches 3000]

Writes the models directly - no notification is sent, and every account
uses an ``example.org`` address. Refuses to run on a database that already
holds teams or Elo matches.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from app.core.permissions import GROUP_ADMIN, GROUP_CAPTAIN, GROUP_PLAYER
from app.elo.models import EloProfile, Match
from app.elo.services.matches import recalculate_all
from app.matchdays.models import Matchday, MatchdayPlayer, Season
from app.penalties.models import Payment, Penalty, PenaltyCatalogItem, TeamCatalogAmount
from app.players.models import Player, PlayerTeam
from app.teams.models import Team, TeamCashier

FIRST = [
    "Anna",
    "Bernd",
    "Carla",
    "Dirk",
    "Eva",
    "Frank",
    "Gina",
    "Hans",
    "Ines",
    "Jonas",
    "Kim",
    "Lars",
    "Mia",
    "Nils",
    "Olga",
    "Paul",
    "Rita",
    "Sven",
    "Tina",
    "Uwe",
    "Vera",
    "Wim",
    "Xenia",
    "Yann",
    "Zoe",
    "Ben",
    "Lea",
    "Max",
    "Ida",
    "Tom",
    "Ute",
    "Jan",
]
LAST = [
    "Bauer",
    "Fischer",
    "Weber",
    "Wolf",
    "Schulz",
    "Koch",
    "Klein",
    "Hahn",
    "Lang",
    "Krause",
    "Braun",
    "Peters",
    "Vogel",
    "Kraft",
    "Link",
]
OPPONENTS = [
    "SV Eichenberg",
    "TSV Musterstadt",
    "DC Bullseye",
    "FC Triple 20",
    "Dart Devils",
    "SG Nord",
]
PASSWORD = "Demo1!demo-pw"


class Command(BaseCommand):
    help = "Fill an empty portal with demo data (teams, seasons, penalties, Elo history)."

    def add_arguments(self, parser):
        parser.add_argument("--years", type=int, default=3)
        parser.add_argument("--matches", type=int, default=3000)
        parser.add_argument("--seed", type=int, default=42)

    @transaction.atomic
    def handle(self, years=3, matches=3000, seed=42, **opts):
        if Team.objects.exists() or Match.objects.exists():
            raise CommandError("The database is not empty - seed_demo only fills an empty portal.")
        rnd = random.Random(seed)
        today = timezone.localdate()
        start = today - timedelta(days=365 * years)
        User = get_user_model()
        groups = {
            g: Group.objects.get_or_create(name=g)[0]
            for g in (GROUP_ADMIN, GROUP_CAPTAIN, GROUP_PLAYER)
        }

        teams = [Team.objects.create(name=f"Bullseye {i}") for i in range(1, 5)]
        seasons = []
        for y in range(years, -1, -1):
            yr = today.year - y
            season, _created = Season.objects.get_or_create(name=f"{yr}/{yr + 1}")
            seasons.append(season)
        Season.objects.update(is_default=False)
        Season.objects.filter(pk=seasons[-1].pk).update(is_default=True)
        for s in seasons:
            s.teams.set(teams)

        names = rnd.sample([f"{f} {lname}" for f in FIRST for lname in LAST], 48)
        players = [Player.objects.create(name=n) for n in names]
        for i, p in enumerate(players):
            for s in seasons:
                PlayerTeam.objects.create(player=p, team=teams[i % 4], season=s)

        def account(email, group, **extra):
            u = User.objects.create_user(
                email=email, password=PASSWORD, approval_status="approved", **extra
            )
            u.groups.add(groups[group])
            u.is_staff = group == GROUP_ADMIN
            u.save()
            return u

        admin = account(
            "demo-admin@example.org", GROUP_ADMIN, full_name="Demo Admin", player_link=players[0]
        )
        captains = [
            account(
                f"captain{i + 1}@example.org",
                GROUP_CAPTAIN,
                team=t,
                player_link=players[i + 1],
                full_name=f"Captain {i + 1}",
            )
            for i, t in enumerate(teams)
        ]
        _members = [
            account(
                f"player{i}@example.org",
                GROUP_PLAYER,
                player_link=players[i],
                full_name=players[i].name,
            )
            for i in range(5, 25)
        ]
        account("elo-only@example.org", GROUP_PLAYER, penalty_access=False, full_name="Club Tablet")
        account(
            "penalty-only@example.org",
            GROUP_PLAYER,
            elo_access=False,
            player_link=players[30],
            full_name=players[30].name,
        )
        for t, c in zip(teams, captains, strict=True):
            TeamCashier.objects.create(team=t, user=c, created_by=admin)

        catalog = [
            PenaltyCatalogItem.objects.create(description=d, amount_eur=Decimal(a))
            for d, a in (
                ("Late", "2"),
                ("Forgot the darts", "3"),
                ("3 or less", "1"),
                ("Bust on 1", "0.5"),
                ("Phone at the board", "1"),
            )
        ]
        for t in teams:
            for item in catalog:
                TeamCatalogAmount.objects.create(
                    team=t, catalog_item=item, amount_eur=item.amount_eur, active=True
                )

        n_penalties = 0
        for s_idx, season in enumerate(seasons):
            for t_idx, team in enumerate(teams):
                roster = [p for i, p in enumerate(players) if i % 4 == t_idx]
                for k in range(10):
                    d = start + timedelta(days=365 * s_idx + 20 * k + t_idx)
                    if d > today:
                        break
                    md = Matchday.objects.create(
                        team=team,
                        season=season,
                        date=d,
                        opponent=rnd.choice(OPPONENTS),
                        created_by=captains[t_idx],
                    )
                    present = rnd.sample(roster, min(8, len(roster)))
                    for p in present:
                        MatchdayPlayer.objects.create(matchday=md, player=p)
                    for _ in range(rnd.randint(1, 6)):
                        item = rnd.choice(catalog)
                        Penalty.objects.create(
                            matchday=md,
                            player=rnd.choice(present),
                            catalog_item=item,
                            description_snapshot=item.description,
                            amount_eur=item.amount_eur,
                            created_by=captains[t_idx],
                        )
                        n_penalties += 1
                for p in roster[:6]:
                    Payment.objects.create(
                        player=p,
                        team=team,
                        season=season,
                        amount_eur=Decimal(rnd.choice(["5", "10", "15"])),
                        created_by=captains[t_idx],
                        received_by=captains[t_idx],
                    )

        elo_players = players[:40]
        for p in elo_players:
            EloProfile.objects.create(
                player=p, start_elo=1200, current_elo=1200.0, entry_date=start
            )
        skill = {p.pk: rnd.gauss(0, 1) for p in elo_players}
        objs = []
        span = (today - start).days
        for i in range(matches):
            a, b = rnd.sample(elo_players, 2)
            pa = 1 / (1 + 10 ** ((skill[b.pk] - skill[a.pk]) * 0.8))
            lo = rnd.randint(0, 2)
            sa, sb = (3, lo) if rnd.random() < pa else (lo, 3)
            d = start + timedelta(days=int(span * i / matches))
            objs.append(
                Match(
                    date=d, player_a=a, player_b=b, best_of_legs=5, score_a=sa, score_b=sb,
                    winner=a if sa > sb else b, loser=b if sa > sb else a, k_factor=32.0,
                    a_180s=rnd.choice([0, 0, 0, 1, 2]), b_180s=rnd.choice([0, 0, 1]),
                    a_high_finishes=[rnd.choice([100, 121, 140, 161, 170])] if sa == 3 and rnd.random() < 0.15 else [],
                    b_low_darts=[rnd.choice([12, 15, 18, 21])] if sb == 3 and rnd.random() < 0.1 else [],
                    a_average=round(rnd.uniform(35, 75), 2), b_average=round(rnd.uniform(35, 75), 2),
                    created_by=admin,
                    created_at=timezone.make_aware(timezone.datetime(d.year, d.month, d.day, 19, 0)) + timedelta(seconds=i),
                )
            )  # fmt: skip
        Match.objects.bulk_create(objs, batch_size=1000)
        recalculate_all()
        EloProfile.objects.filter(player=elo_players[-1]).update(disabled=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data: {len(teams)} teams, {len(seasons)} seasons, {len(players)} players, "
                f"{n_penalties} penalties, {len(objs)} Elo matches. Password of every demo account: {PASSWORD}"
            )
        )
