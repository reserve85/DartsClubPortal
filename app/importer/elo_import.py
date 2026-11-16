"""Import an EloRankingSystem SQLite database into the Elo module.

What happens (one transaction - all or nothing):

1. Players: matched to existing portal people by name (case-insensitive),
   otherwise created - unless the admin decided per player in the preview
   (``player_map``: Elo player id -> portal player id or "new"). Each gets an EloProfile with the old start Elo,
   entry date (fallback: creation date, never after the first match),
   disabled flag and disable periods.
2. Matches: copied with date, original creation time (keeps the timeline
   order), result, format, K-factor and dart statistics.
3. Accounts: ADMIN -> portal Admin, USER -> User with Elo access and read-only penalty pages;
   the SYSTEM bootstrap account is skipped (the portal has its own).
   Passwords keep working (argon2 hashes are taken over), old printed QR
   codes keep working (legacy login name / id are stored).
4. The whole Elo history is recalculated and compared with the stored
   values of the old system (verification report).

``dry_run=True`` runs everything and rolls back (preview).
"""

import json
import re
import sqlite3
from datetime import UTC, date, datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.functions import Lower
from django.utils import timezone

from app.core.models import AuditAction
from app.core.permissions import GROUP_ADMIN, GROUP_PLAYER
from app.core.services import log_action
from app.elo.models import EloDisablePeriod, EloProfile, Match
from app.elo.services.matches import recalculate_all
from app.importer.report import ImportAborted, ImportReport
from app.players.models import Player

TOLERANCE = 0.01


class _Rollback(Exception):
    pass


def unpack_backup(path: str) -> str:
    """An Elo backup ZIP -> path of its database.db; club logos are taken over.

    A plain database file is returned unchanged.
    """
    import os
    import tempfile
    import zipfile

    if not zipfile.is_zipfile(path):
        return path
    from app.core.branding import save_logo

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        db_name = next((n for n in names if n.rsplit("/", 1)[-1] == "database.db"), None)
        if db_name is None:
            raise ImportAborted("The ZIP file contains no database.db.")
        target = os.path.join(tempfile.mkdtemp(prefix="elo-import-"), "database.db")
        with zf.open(db_name) as src, open(target, "wb") as dst:
            dst.write(src.read())
        for name in names:
            base = name.rsplit("/", 1)[-1]
            if base.startswith("club_logo") and base.lower().endswith((".png", ".jpg", ".jpeg")):
                try:
                    save_logo("dark" if "_dark" in base else "light", zf.read(name))
                except ValueError:
                    pass
    return target


def _connect(path: str) -> sqlite3.Connection:
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    except sqlite3.DatabaseError as exc:
        raise ImportAborted(f"Not a readable SQLite database: {exc}") from exc
    if not {"players", "matches"} <= tables:
        raise ImportAborted("This is not an Elo database (tables 'players'/'matches' missing).")
    return con


def _columns(con, table) -> set[str]:
    return {r[1] for r in con.execute(f"pragma table_info({table})")}


def _rows(con, table):
    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    if table not in tables:
        return []
    return [dict(r) for r in con.execute(f"select * from {table} order by id")]


def _date(value):
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _dt(value):
    if value in (None, ""):
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = datetime.fromisoformat(text[:19])
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, UTC)
    return parsed


def _list(value) -> list:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [int(v) for v in value]
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return []
    return [int(v) for v in data] if isinstance(data, list) else []


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", name.strip().lower()).strip("-") or "user"


def import_elo(
    path: str,
    *,
    dry_run: bool = False,
    replace: bool = False,
    email_domain: str = "elo.invalid",
    account_map: dict | None = None,
    player_map: dict | None = None,
    actor=None,
) -> ImportReport:
    """``account_map``: Elo login name -> existing portal account (pk or e-mail)."""
    report = ImportReport(kind="Elo", dry_run=dry_run)
    if not dry_run:
        path = unpack_backup(path)
    else:
        import zipfile

        if zipfile.is_zipfile(path):
            path = _db_from_zip_for_preview(path)
    con = _connect(path)
    try:
        with transaction.atomic():
            _run(
                con,
                report,
                replace=replace,
                email_domain=email_domain,
                account_map=account_map or {},
                player_choice={str(k): str(v) for k, v in (player_map or {}).items() if v},
                actor=actor,
            )
            if dry_run:
                raise _Rollback
    except _Rollback:
        pass
    finally:
        con.close()
    return report


def _db_from_zip_for_preview(path: str) -> str:
    """Preview: only extract database.db (logos are taken over on the real run)."""
    import os
    import tempfile
    import zipfile

    with zipfile.ZipFile(path) as zf:
        db_name = next((n for n in zf.namelist() if n.rsplit("/", 1)[-1] == "database.db"), None)
        if db_name is None:
            raise ImportAborted("The ZIP file contains no database.db.")
        target = os.path.join(tempfile.mkdtemp(prefix="elo-preview-"), "database.db")
        with zf.open(db_name) as src, open(target, "wb") as dst:
            dst.write(src.read())
    return target


def elo_accounts(path: str) -> list[dict]:
    """Accounts of an Elo database (for the mapping step of the import page)."""
    import zipfile

    if zipfile.is_zipfile(path):
        path = _db_from_zip_for_preview(path)
    con = _connect(path)
    try:
        return [
            {"id": r["id"], "username": r["username"], "role": str(r["role"]).upper()}
            for r in _rows(con, "users")
            if str(r["role"]).upper() != "SYSTEM"
        ]
    finally:
        con.close()


def elo_player_suggestions(path: str) -> list[dict]:
    """Elo players + the portal person each one will be merged with (preview).

    ``match`` is the exact (case-insensitive) name match the import would
    use; without one, ``suggestion`` names a similar portal player (e.g. a
    different spelling) so the admin can merge it by hand.
    """
    import difflib
    import zipfile

    if zipfile.is_zipfile(path):
        path = _db_from_zip_for_preview(path)
    con = _connect(path)
    try:
        rows = _rows(con, "players")
    finally:
        con.close()
    portal = {p.pk: p.name for p in Player.objects.filter(elo__isnull=True).order_by("name")}
    by_lower = {name.strip().lower(): pk for pk, name in portal.items()}
    out = []
    for r in rows:
        name = (r["name"] or "").strip()
        exact = by_lower.get(name.lower())
        suggestion = None
        if exact is None and portal:
            scored = sorted(
                (
                    (difflib.SequenceMatcher(None, name.lower(), n.lower()).ratio(), pk)
                    for pk, n in portal.items()
                ),
                reverse=True,
            )
            if scored and scored[0][0] >= 0.75:
                suggestion = scored[0][1]
        out.append({"id": r["id"], "name": name, "match": exact, "suggestion": suggestion})
    return out


def _run(
    con,
    report: ImportReport,
    *,
    replace: bool,
    email_domain: str,
    account_map: dict,
    actor,
    player_choice: dict | None = None,
) -> None:
    player_choice = player_choice or {}
    if EloProfile.objects.exists() or Match.objects.exists():
        if not replace:
            raise ImportAborted(
                "The portal already contains Elo data. Use 'replace' to delete it first."
            )
        Match.objects.all().delete()
        EloDisablePeriod.objects.all().delete()
        EloProfile.objects.all().delete()
        report.warnings.append("Existing Elo data was deleted before the import (replace).")

    src_players = _rows(con, "players")
    src_matches = _rows(con, "matches")
    src_users = _rows(con, "users")
    src_periods = _rows(con, "player_disable_periods")

    # ---- first match per old player (entry date must not be later) -----
    first_match: dict[int, date] = {}
    for m in src_matches:
        d = _date(m["date"])
        for pid in (m["player_a_id"], m["player_b_id"]):
            if pid not in first_match or d < first_match[pid]:
                first_match[pid] = d

    # ---- players -------------------------------------------------------
    by_name = {}
    for p in Player.objects.annotate(n=Lower("name")).filter(elo__isnull=True):
        by_name.setdefault(p.n.strip(), p)
    player_map: dict[int, Player] = {}
    seen_names: set[str] = set()
    for row in src_players:
        name = (row["name"] or "").strip() or f"Player {row['id']}"
        key = name.lower()
        if key in seen_names:
            name = f"{name} ({row['id']})"
            key = name.lower()
            report.warnings.append(
                f"Duplicate player name in the Elo database, renamed to '{name}'."
            )
        seen_names.add(key)
        choice = player_choice.get(str(row["id"]))
        if choice == "new":
            person = None  # the admin wants a separate person
        elif choice:
            person = Player.objects.filter(pk=int(choice), elo__isnull=True).first()
            if person is None:
                raise ImportAborted(
                    f"The portal player chosen for '{name}' does not exist or already has Elo data."
                )
            by_name = {k: v for k, v in by_name.items() if v.pk != person.pk}
        else:
            person = by_name.pop(key, None)
        if person is not None:
            report.matched.append(("player", row["name"], person.name))
            report.add("players matched")
        else:
            person = Player.objects.create(name=name)
            report.created.append(("player", name))
            report.add("players created")
        entry = (
            _date(row.get("entry_date")) or (_dt(row.get("created_at")) or timezone.now()).date()
        )
        if row["id"] in first_match and entry > first_match[row["id"]]:
            report.warnings.append(
                f"Entry date of '{name}' moved to the first match ({first_match[row['id']]})."
            )
            entry = first_match[row["id"]]
        profile = EloProfile.objects.create(
            player=person,
            start_elo=int(row.get("start_elo") or 1200),
            current_elo=float(row.get("start_elo") or 1200),
            entry_date=entry,
            disabled=bool(row.get("disabled")),
        )
        player_map[row["id"]] = person
        for period in (pp for pp in src_periods if pp["player_id"] == row["id"]):
            EloDisablePeriod.objects.create(
                profile=profile,
                disabled_from=_date(period["disabled_from"]),
                disabled_to=_date(period.get("disabled_to")),
            )
        if profile.disabled and not profile.disable_periods.exists():
            EloDisablePeriod.objects.create(profile=profile, disabled_from=timezone.localdate())

    # ---- accounts --------------------------------------------------------
    user_map = _import_users(src_users, report, email_domain, account_map)

    # ---- matches ---------------------------------------------------------
    stored: dict[int, tuple] = {}
    new_matches = []
    for m in src_matches:
        a, b = player_map.get(m["player_a_id"]), player_map.get(m["player_b_id"])
        if a is None or b is None:
            report.warnings.append(f"Match {m['id']} skipped: unknown player.")
            continue
        winner = a if m["winner_id"] == m["player_a_id"] else b
        created = _dt(m.get("created_at")) or timezone.make_aware(
            datetime.combine(_date(m["date"]), datetime.min.time())
        )
        obj = Match(
            date=_date(m["date"]),
            player_a=a,
            player_b=b,
            best_of_legs=int(m.get("best_of_legs") or 5),
            score_a=m.get("player1_score"),
            score_b=m.get("player2_score"),
            winner=winner,
            loser=b if winner is a else a,
            k_factor=float(m.get("k_factor") or 32.0),
            a_180s=int(m.get("player_a_180s") or 0),
            b_180s=int(m.get("player_b_180s") or 0),
            a_high_finishes=_list(m.get("player_a_high_finishes")),
            b_high_finishes=_list(m.get("player_b_high_finishes")),
            a_low_darts=_list(m.get("player_a_low_darts")),
            b_low_darts=_list(m.get("player_b_low_darts")),
            a_average=m.get("player_a_average"),
            b_average=m.get("player_b_average"),
            created_by=user_map.get(m.get("created_by")),
            created_at=created,
            elo_after_a=float(m.get("elo_after_a") or 0),
            elo_after_b=float(m.get("elo_after_b") or 0),
        )
        new_matches.append((m["id"], obj))
        stored[m["id"]] = (float(m.get("elo_after_a") or 0), float(m.get("elo_after_b") or 0))
    Match.objects.bulk_create([o for _id, o in new_matches], batch_size=500)
    report.add("matches imported", len(new_matches))

    # ---- recalculation + verification -----------------------------------
    recalculate_all(user=actor if getattr(actor, "is_authenticated", False) else None)
    worst, mismatches = 0.0, 0
    for src_id, obj in new_matches:
        obj.refresh_from_db(fields=["elo_after_a", "elo_after_b"])
        sa, sb = stored[src_id]
        diff = max(abs(obj.elo_after_a - sa), abs(obj.elo_after_b - sb))
        worst = max(worst, diff)
        if diff > TOLERANCE:
            mismatches += 1
    report.checks.append(
        (
            "Elo history recalculated",
            mismatches == 0,
            (
                f"{len(new_matches)} matches, {mismatches} differ from the old system "
                f"(largest difference {worst:.4f})"
            ),
        )
    )
    cur_diff = 0.0
    for row in src_players:
        person = player_map[row["id"]]
        prof = EloProfile.objects.get(player=person)
        if row.get("current_elo") is not None:
            cur_diff = max(cur_diff, abs(prof.current_elo - float(row["current_elo"])))
    report.checks.append(
        (
            "Current Elo of every player",
            cur_diff <= TOLERANCE,
            f"largest difference {cur_diff:.4f}",
        )
    )
    report.checks.append(
        (
            "Counts",
            Match.objects.count() == len(new_matches)
            and EloProfile.objects.count() == len(src_players),
            f"{EloProfile.objects.count()} players, {Match.objects.count()} matches in the portal",
        )
    )
    log_action(
        AuditAction.DATA_IMPORTED,
        user=actor if getattr(actor, "is_authenticated", False) else None,
        metadata={"kind": "elo", "counts": report.counts},
    )


def _import_users(src_users, report: ImportReport, email_domain: str, account_map: dict) -> dict:
    User = get_user_model()
    groups = {
        GROUP_ADMIN: Group.objects.get_or_create(name=GROUP_ADMIN)[0],
        GROUP_PLAYER: Group.objects.get_or_create(name=GROUP_PLAYER)[0],
    }
    user_map = {}
    for row in src_users:
        role = str(row.get("role") or "USER").upper()
        username = (row.get("username") or "").strip()
        if role == "SYSTEM":
            report.add("accounts skipped (system account)")
            continue
        user = None
        target = account_map.get(username)
        if target:
            user = (
                User.objects.filter(pk=int(target)).first()
                if str(target).isdigit()
                else User.objects.filter(email__iexact=str(target)).first()
            )
            if user is None:
                raise ImportAborted(f"Account mapping for '{username}': '{target}' not found.")
        if user is None and "@" in username:
            user = User.objects.filter(email__iexact=username).first()
        if user is None:
            user = User.objects.filter(legacy_username=username).first()
        if user is not None:
            report.matched.append(("account", username, user.email))
            report.add("accounts matched")
        else:
            email = username.lower() if "@" in username else f"{_slug(username)}@{email_domain}"
            n = 2
            while User.objects.filter(email__iexact=email).exists():
                email = f"{_slug(username)}-{n}@{email_domain}"
                n += 1
            user = User(email=email, full_name=username, approval_status="approved")
            report.created.append(("account", f"{username} -> {email}"))
            report.add("accounts created")
            pw = row.get("password_hash") or ""
            if pw.startswith("$argon2"):
                user.password = "argon2" + pw
            else:
                user.set_unusable_password()
                report.warnings.append(f"Account '{username}': password could not be taken over.")
            user.is_active = bool(row.get("active", True))
            # Penalty pages are read-only for users anyway (only admins and
            # captains enter penalties), so imported accounts may view them.
            user.penalty_access = True
            user.elo_access = True
        if not User.objects.filter(legacy_username=username).exclude(pk=user.pk).exists():
            user.legacy_username = username
        if not User.objects.filter(legacy_elo_id=row["id"]).exclude(pk=user.pk).exists():
            user.legacy_elo_id = row["id"]
        user.save()
        if role == "ADMIN":
            user.groups.add(groups[GROUP_ADMIN])
        elif not user.groups.exists():
            user.groups.add(groups[GROUP_PLAYER])
        user_map[row["id"]] = user
    return user_map
