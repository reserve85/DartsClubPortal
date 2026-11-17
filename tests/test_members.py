"""Members: every person with teams, Elo and account in one place."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from app.accounts.models import Invitation
from app.core.models import AuditAction, AuditLog
from app.core.permissions import GROUP_ADMIN
from app.elo.models import EloProfile
from app.players.models import Player
from app.players.services import assign_teams, teams_for
from tests.conftest import inertia_props

pytestmark = pytest.mark.django_db
User = get_user_model()
LIST = reverse("players:player_list")
CREATE = reverse("players:player_create")


def _edit(player):
    return reverse("players:player_update", args=[player.pk])


def _admin(email, **areas):
    user = User.objects.create_user(email=email, password="pw", approval_status="approved", **areas)
    user.groups.add(Group.objects.get(name=GROUP_ADMIN))
    client = Client()
    client.force_login(user)
    return user, client


# ---------------------------------------------------------------- list
def test_list_shows_teams_elo_and_account(admin_client, role_groups, team, season):
    linked = Player.objects.create(name="Anna Linked", team=team, season=season)
    User.objects.create_user(email="anna@example.com", password="pw", player_link=linked)
    EloProfile.objects.create(
        player=linked, start_elo=1500, current_elo=1512.4, entry_date=timezone.localdate()
    )
    Player.objects.create(name="Bert Offline")
    rows = {r["name"]: r for r in inertia_props(admin_client.get(LIST))["members"]}
    anna, bert = rows["Anna Linked"], rows["Bert Offline"]
    assert anna["teams"] == [team.name] and anna["elo"] == {"current": 1512, "disabled": False}
    assert anna["account"] == {"state": "linked", "email": "anna@example.com", "active": True}
    assert bert["account"]["state"] == "none" and bert["elo"] is None and bert["teams"] == []
    assert anna["editUrl"] == _edit(linked)


def test_list_marks_invited_members(admin_client, role_groups, admin_user):
    player = Player.objects.create(name="Clara Invited")
    from app.accounts.services import create_invitation

    create_invitation(
        email="clara@example.com", role="Player", team=None, player=player,
        language="de", invited_by=admin_user,
    )  # fmt: skip
    rows = {r["name"]: r for r in inertia_props(admin_client.get(LIST))["members"]}
    assert rows["Clara Invited"]["account"] == {
        "state": "invited",
        "email": "clara@example.com",
        "active": True,
    }


def test_list_is_for_every_admin_area_only(role_groups, captain_client, player_client):
    for area in ("admin_elo", "admin_penalty", "admin_portal"):
        _user, client = _admin(f"{area}@example.com", **{area: True})
        assert client.get(LIST).status_code == 200, area
    assert captain_client.get(LIST).status_code == 403
    assert player_client.get(LIST).status_code == 403


def test_menu_has_members_for_admins(admin_client, captain_client):
    def hrefs(client):
        nav = inertia_props(client.get(reverse("rights")))["nav"]
        return [i["href"] for g in nav for i in g["items"]]

    assert LIST in hrefs(admin_client)
    assert LIST not in hrefs(captain_client)


# ---------------------------------------------------------------- create
def test_admin_creates_member_with_team_elo_and_invitation(admin_client, team, season):
    mail.outbox.clear()
    entry = (timezone.localdate() - timedelta(days=3)).isoformat()
    response = admin_client.post(
        CREATE,
        {
            "name": "  Dora New ",
            "team": team.pk,
            "elo": "on",
            "start_elo": 1350,
            "entry_date": entry,
            "invite": "on",
            "email": "Dora@Example.com",
            "language": "en",
        },
    )
    player = Player.objects.get(name="Dora New")
    assert response.status_code == 302 and response["Location"] == _edit(player)
    assert teams_for(player, season) == [team]
    profile = EloProfile.objects.get(player=player)
    assert (profile.start_elo, profile.current_elo, profile.entry_date.isoformat()) == (
        1350,
        1350.0,
        entry,
    )
    invitation = Invitation.objects.get(player=player)
    assert invitation.user.email == "dora@example.com" and invitation.role == "Player"
    assert [m.to for m in mail.outbox] == [["dora@example.com"]]
    assert AuditLog.objects.filter(action=AuditAction.PLAYER_CREATED, target_id=player.pk).exists()


def test_create_without_options_makes_an_offline_member(admin_client):
    assert admin_client.post(CREATE, {"name": "Emil Offline"}).status_code == 302
    player = Player.objects.get(name="Emil Offline")
    assert not EloProfile.objects.filter(player=player).exists()
    assert not Invitation.objects.filter(player=player).exists()
    assert not player.teams.exists()


def test_duplicate_name_is_refused(admin_client):
    Player.objects.create(name="Fritz Twice")
    props = inertia_props(admin_client.post(CREATE, {"name": "fritz twice"}))
    assert "name" in props["errors"]
    assert Player.objects.filter(name__iexact="fritz twice").count() == 1


def test_taken_email_creates_nothing(admin_client, player_user):
    props = inertia_props(
        admin_client.post(
            CREATE, {"name": "Gina Mail", "invite": "on", "email": player_user.email, "elo": "on"}
        )
    )
    assert "email" in props["errors"]
    assert not Player.objects.filter(name="Gina Mail").exists()


def test_invitation_needs_an_address(admin_client):
    props = inertia_props(admin_client.post(CREATE, {"name": "Hans Nomail", "invite": "on"}))
    assert "email" in props["errors"]
    assert not Player.objects.filter(name="Hans Nomail").exists()


def test_future_entry_date_is_refused(admin_client):
    tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
    props = inertia_props(
        admin_client.post(CREATE, {"name": "Ida Future", "elo": "on", "entry_date": tomorrow})
    )
    assert "entry_date" in props["errors"]
    assert not Player.objects.filter(name="Ida Future").exists()


def test_elo_admin_cannot_invite_and_penalty_admin_cannot_add_elo(role_groups, team):
    mail.outbox.clear()
    _u, elo_client = _admin("elo@example.com", admin_elo=True)
    props = inertia_props(elo_client.get(CREATE))
    assert props["canElo"] is True and props["canInvite"] is False and props["teams"] == []
    elo_client.post(
        CREATE, {"name": "Jan Elo", "elo": "on", "invite": "on", "email": "j@example.com"}
    )
    jan = Player.objects.get(name="Jan Elo")
    assert EloProfile.objects.filter(player=jan).exists()
    assert not Invitation.objects.filter(player=jan).exists() and not mail.outbox

    _u, pen_client = _admin("pen@example.com", admin_penalty=True)
    pen_client.post(CREATE, {"name": "Kai Penalty", "elo": "on", "team": team.pk})
    kai = Player.objects.get(name="Kai Penalty")
    assert not EloProfile.objects.filter(player=kai).exists()
    assert list(kai.teams.all()) == [team]


# ---------------------------------------------------------------- one member
def test_member_page_sections_follow_the_areas(role_groups, team):
    player = Player.objects.create(name="Lena Sections")
    _u, elo_client = _admin("elo2@example.com", admin_elo=True)
    props = inertia_props(elo_client.get(_edit(player)))
    assert props["elo"] is not None and props["account"] is None
    assert all(not t["editable"] for t in props["teams"])
    _u, portal_client = _admin("portal@example.com", admin_portal=True)
    props = inertia_props(portal_client.get(_edit(player)))
    assert props["elo"] is None and props["account"] is not None


def test_rename_keeps_elo_and_refuses_duplicates(admin_client):
    player = Player.objects.create(name="Max Old")
    EloProfile.objects.create(
        player=player, start_elo=1200, current_elo=1200.0, entry_date=timezone.localdate()
    )
    Player.objects.create(name="Taken Name")
    props = inertia_props(
        admin_client.post(
            _edit(player), {"section": "basics", "name": "taken name", "active": "on"}
        )
    )
    assert "name" in props["errors"]["basics"]
    admin_client.post(_edit(player), {"section": "basics", "name": "Max New", "active": ""})
    player.refresh_from_db()
    assert player.name == "Max New" and player.active is False
    assert EloProfile.objects.get(player=player).player.name == "Max New"


def test_teams_section_changes_only_editable_teams(captain_client, team, other_team, season):
    player = Player.objects.create(name="Nora Teams")
    assign_teams(player, [team, other_team], season=season)
    # captain of `team`: may drop their own team, the other one stays
    captain_client.post(_edit(player), {"section": "teams", "teams": []})
    assert teams_for(player, season) == [other_team]


def test_elo_section_adds_and_toggles(admin_client):
    player = Player.objects.create(name="Otto Elo")
    admin_client.post(
        _edit(player), {"section": "elo", "action": "add", "start_elo": 1400, "entry_date": ""}
    )
    profile = EloProfile.objects.get(player=player)
    assert profile.start_elo == 1400 and not profile.disabled
    admin_client.post(_edit(player), {"section": "elo", "action": "toggle"})
    profile.refresh_from_db()
    assert profile.disabled
    admin_client.post(_edit(player), {"section": "elo", "action": "toggle"})
    profile.refresh_from_db()
    assert not profile.disabled


def test_elo_section_needs_the_elo_area(role_groups):
    player = Player.objects.create(name="Paul Guard")
    _u, pen_client = _admin("pen2@example.com", admin_penalty=True)
    response = pen_client.post(_edit(player), {"section": "elo", "action": "add"})
    assert response.status_code == 403
    assert not EloProfile.objects.filter(player=player).exists()


def test_account_section_invites_links_and_unlinks(admin_client, role_groups):
    mail.outbox.clear()
    player = Player.objects.create(name="Quinn Account")
    admin_client.post(
        _edit(player), {"section": "account", "action": "invite", "email": "quinn@example.com"}
    )
    assert Invitation.objects.get(player=player).user.email == "quinn@example.com"
    assert [m.to for m in mail.outbox] == [["quinn@example.com"]]
    props = inertia_props(admin_client.get(_edit(player)))
    assert props["account"]["invitation"]["email"] == "quinn@example.com"

    other = Player.objects.create(name="Rita Link")
    account = User.objects.create_user(email="rita@example.com", password="pw")
    linkable = inertia_props(admin_client.get(_edit(other)))["account"]["linkable"]
    assert str(account.pk) in [c["value"] for c in linkable]
    admin_client.post(_edit(other), {"section": "account", "action": "link", "user": account.pk})
    account.refresh_from_db()
    assert account.player_link == other
    admin_client.post(_edit(other), {"section": "account", "action": "unlink"})
    account.refresh_from_db()
    assert account.player_link is None


def test_account_section_needs_the_portal_area(role_groups):
    player = Player.objects.create(name="Sven Guard")
    _u, elo_client = _admin("elo3@example.com", admin_elo=True)
    response = elo_client.post(
        _edit(player), {"section": "account", "action": "invite", "email": "s@example.com"}
    )
    assert response.status_code == 403
    assert not Invitation.objects.filter(player=player).exists()


def test_invite_with_taken_address_shows_an_error(admin_client, player_user):
    player = Player.objects.create(name="Tina Taken")
    props = inertia_props(
        admin_client.post(
            _edit(player), {"section": "account", "action": "invite", "email": player_user.email}
        )
    )
    assert "email" in props["errors"]["account"]


def test_player_cannot_open_member_pages(player_client):
    player = Player.objects.create(name="Uwe Private")
    assert player_client.get(_edit(player)).status_code == 403
    assert player_client.get(CREATE).status_code == 403


# ---------------------------------------------------------------- quick actions
QUICK = reverse("players:member_quick_add")


def test_quick_add_creates_several_with_defaults(admin_client, team, season):
    Player.objects.create(name="Already Here")
    response = admin_client.post(
        QUICK,
        {
            "names": "Vera One\n  vera   one \nWalter Two, already here\n\n",
            "team": team.pk,
            "elo": "on",
        },
    )
    assert response.status_code == 302 and response["Location"] == LIST
    vera, walter = Player.objects.get(name="Vera One"), Player.objects.get(name="Walter Two")
    for p in (vera, walter):
        assert teams_for(p, season) == [team]
        assert EloProfile.objects.filter(player=p).exists()
    assert Player.objects.filter(name__iexact="already here").count() == 1  # skipped


def test_quick_add_respects_the_areas(role_groups, captain_client, team):
    _u, pen = _admin("pen3@example.com", admin_penalty=True)
    pen.post(QUICK, {"names": "Xaver Pen", "team": team.pk, "elo": "on"})
    xaver = Player.objects.get(name="Xaver Pen")
    assert list(xaver.teams.all()) == [team]
    assert not EloProfile.objects.filter(player=xaver).exists()  # no Elo area
    assert captain_client.post(QUICK, {"names": "Yvonne Cap"}).status_code == 403
    assert not Player.objects.filter(name="Yvonne Cap").exists()


def test_list_offers_defaults_and_counts(admin_client, team, role_groups):
    User.objects.create_user(email="wait@example.com", password="pw")  # pending by default
    props = inertia_props(admin_client.get(LIST))
    assert props["defaultTeam"] == str(team.pk)
    assert props["can"] == {"elo": True, "invite": True}
    assert props["pendingApprovals"] >= 1


def test_row_actions_return_to_the_list(admin_client, player_user):
    player = Player.objects.create(name="Zora Row")
    response = admin_client.post(_edit(player), {"section": "elo", "action": "add", "next": LIST})
    assert response.status_code == 302 and response["Location"] == LIST
    assert EloProfile.objects.filter(player=player).exists()
    # an error from the list comes back as a message, not as the member page
    response = admin_client.post(
        _edit(player),
        {"section": "account", "action": "invite", "email": player_user.email, "next": LIST},
    )
    assert response.status_code == 302 and response["Location"] == LIST
    assert not Invitation.objects.filter(player=player).exists()


def test_foreign_next_is_ignored(admin_client):
    player = Player.objects.create(name="Next Guard")
    response = admin_client.post(
        _edit(player), {"section": "elo", "action": "add", "next": "//evil.example.com/"}
    )
    assert response["Location"] == _edit(player)


def test_an_email_alone_sends_the_invitation(admin_client):
    mail.outbox.clear()
    admin_client.post(CREATE, {"name": "Ada Mail", "email": "ada@example.com"})
    player = Player.objects.get(name="Ada Mail")
    assert Invitation.objects.get(player=player).user.email == "ada@example.com"
    assert [m.to for m in mail.outbox] == [["ada@example.com"]]
