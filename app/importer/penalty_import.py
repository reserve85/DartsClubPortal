"""Import a DartsPenaltySystem SQLite database into the portal.

The penalty system and the portal share their schema history, so the old
file is copied to a temporary database, brought to the current schema with
the normal migrations and then copied row by row into the portal - with new
ids where needed and these merges (no duplicates):

- accounts by e-mail, people by name, teams and seasons by name,
  role groups by name, catalog items by (description, type),
- everything else (matchdays, penalties, payments, cashiers, invitations,
  audit log) is copied and re-linked.

Everything runs in ONE transaction; ``dry_run=True`` rolls back (preview).
Recommended order for a switch-over: penalty database first (it carries the
accounts with e-mail addresses), then the Elo database.
"""

import contextlib
import os
import shutil
import sqlite3
import tempfile

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connections, transaction

from app.core.models import AuditAction
from app.core.services import log_action
from app.importer.report import ImportAborted, ImportReport

ALIAS = "penalty_import_source"

# Copy order (parents first) and how a row is matched to an existing one.
PLAN = [
    ("auth.Group", ("name",)),
    ("teams.Team", ("name",)),
    ("matchdays.Season", ("name",)),
    ("players.Player", ("name",)),
    ("accounts.User", ("email",)),
    ("account.EmailAddress", ("user", "email")),
    ("accounts.Invitation", None),
    ("teams.TeamCashier", None),
    ("players.PlayerTeam", ("player", "team", "season")),
    ("matchdays.Matchday", None),
    ("matchdays.MatchdayPlayer", ("matchday", "player")),
    ("penalties.PenaltyCatalogItem", ("description", "type")),
    ("penalties.TeamCatalogAmount", ("team", "catalog_item")),
    ("penalties.Penalty", None),
    ("penalties.Payment", None),
    ("core.AuditLog", None),
]
CASE_INSENSITIVE = {"name", "email"}


class _Rollback(Exception):
    pass


@contextlib.contextmanager
def _source_db(path: str):
    """Temporary migrated copy of the penalty database as an extra alias."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        con.close()
    except sqlite3.DatabaseError as exc:
        raise ImportAborted(f"Not a readable SQLite database: {exc}") from exc
    if not {"penalties_penalty", "accounts_user", "players_player"} <= tables:
        raise ImportAborted("This is not a penalty database (penalty tables missing).")
    tmpdir = tempfile.mkdtemp(prefix="penalty-import-")
    copy = os.path.join(tmpdir, "source.sqlite3")
    shutil.copyfile(path, copy)
    cfg = dict(settings.DATABASES["default"])
    cfg.update({"NAME": copy, "TEST": {"NAME": copy}})
    settings.DATABASES[ALIAS] = cfg
    connections.settings = connections.configure_settings(settings.DATABASES)
    try:
        call_command("migrate", database=ALIAS, verbosity=0, interactive=False)
        yield ALIAS
    finally:
        with contextlib.suppress(Exception):
            connections[ALIAS].close()
        settings.DATABASES.pop(ALIAS, None)
        with contextlib.suppress(Exception):
            del connections[ALIAS]
        shutil.rmtree(tmpdir, ignore_errors=True)


@contextlib.contextmanager
def _keep_timestamps(model):
    """auto_now/auto_now_add would overwrite the original times."""
    saved = []
    for f in model._meta.concrete_fields:
        if getattr(f, "auto_now", False) or getattr(f, "auto_now_add", False):
            saved.append((f, f.auto_now, f.auto_now_add))
            f.auto_now = f.auto_now_add = False
    try:
        yield
    finally:
        for f, now, now_add in saved:
            f.auto_now, f.auto_now_add = now, now_add


def import_penalty(path: str, *, dry_run: bool = False, actor=None) -> ImportReport:
    report = ImportReport(kind="Penalty", dry_run=dry_run)
    with _source_db(path) as alias:
        try:
            with transaction.atomic():
                _run(alias, report, actor)
                if dry_run:
                    raise _Rollback
        except _Rollback:
            pass
    return report


def _key(obj, fields, maps) -> tuple:
    out = []
    for name in fields:
        f = obj._meta.get_field(name)
        value = getattr(obj, f.attname)
        if f.is_relation:
            value = maps.get(f.related_model._meta.label, {}).get(value, value)
        elif name in CASE_INSENSITIVE and isinstance(value, str):
            value = value.strip().lower()
        out.append(value)
    return tuple(out)


def _run(alias: str, report: ImportReport, actor) -> None:
    maps: dict[str, dict] = {}
    for label, merge_fields in PLAN:
        model = apps.get_model(label)
        src = list(model._base_manager.using(alias).all().order_by("pk"))
        maps[label] = {}
        existing = {}
        if merge_fields:
            for obj in model._base_manager.all():
                existing[_key(obj, merge_fields, {})] = obj.pk
        to_create, pending = [], []
        for obj in src:
            old_pk = obj.pk
            for f in model._meta.concrete_fields:
                if f.is_relation and f.related_model is not None:
                    rel = f.related_model._meta.label
                    if rel in maps:
                        val = getattr(obj, f.attname)
                        if val is not None:
                            setattr(obj, f.attname, maps[rel].get(val))
            if merge_fields:
                key = _key(obj, merge_fields, {})
                if key in existing:
                    maps[label][old_pk] = existing[key]
                    report.add(f"{model._meta.verbose_name_plural} matched")
                    if label in ("players.Player", "accounts.User"):
                        report.matched.append((label.split(".")[1].lower(), str(obj), str(obj)))
                    continue
            if label == "penalties.TeamCatalogAmount" and obj.amount_eur is None:
                # legacy row "use the catalog amount" -> store that amount
                item = apps.get_model("penalties.PenaltyCatalogItem").objects.get(
                    pk=obj.catalog_item_id
                )
                obj.amount_eur = item.amount_eur
                report.add("legacy team amounts healed")
            missing = [
                f.name
                for f in model._meta.concrete_fields
                if not f.null
                and not f.primary_key
                and getattr(obj, f.attname) is None
                and not f.has_default()
            ]
            if missing:
                report.warnings.append(f"{label} #{old_pk} skipped: empty {', '.join(missing)}.")
                continue
            if (
                label == "matchdays.Season"
                and getattr(obj, "is_default", False)
                and model._base_manager.filter(is_default=True).exists()
            ):
                obj.is_default = False
            obj.pk = None
            obj.id = None
            to_create.append(obj)
            pending.append(old_pk)
        with _keep_timestamps(model):
            created = model._base_manager.bulk_create(to_create, batch_size=500)
        for old_pk, obj in zip(pending, created, strict=True):
            maps[label][old_pk] = obj.pk
            if merge_fields:
                existing[_key(obj, merge_fields, {})] = obj.pk
        if created:
            report.add(f"{model._meta.verbose_name_plural} imported", len(created))
        _copy_m2m(model, alias, maps)

    # Group memberships of imported accounts keep is_staff in sync (signals).
    from app.accounts.models import User

    for user in User.objects.filter(pk__in=list(maps["accounts.User"].values())):
        user.is_staff = user.groups.filter(name="Admin").exists() or user.is_superuser
        user.save(update_fields=["is_staff"])

    src_counts = {
        label: apps.get_model(label)._base_manager.using(alias).count()
        for label in ("penalties.Penalty", "penalties.Payment", "matchdays.Matchday")
    }
    for label, n in src_counts.items():
        mapped = len(maps[label])
        report.checks.append(
            (f"{label.split('.')[1]} rows", mapped == n, f"{mapped} of {n} copied")
        )
    log_action(
        AuditAction.DATA_IMPORTED,
        user=actor if getattr(actor, "is_authenticated", False) else None,
        metadata={"kind": "penalty", "counts": report.counts},
    )


def _copy_m2m(model, alias, maps) -> None:
    """Auto-created many-to-many tables (user groups, season teams)."""
    for f in model._meta.many_to_many:
        through = f.remote_field.through
        if not through._meta.auto_created:
            continue
        target_label = f.related_model._meta.label
        if target_label not in maps:
            continue
        src_col = f.m2m_field_name() + "_id"
        dst_col = f.m2m_reverse_field_name() + "_id"
        rows = []
        for row in through._base_manager.using(alias).values(src_col, dst_col):
            a = maps[model._meta.label].get(row[src_col])
            b = maps[target_label].get(row[dst_col])
            if a and b:
                rows.append(through(**{src_col: a, dst_col: b}))
        through._base_manager.bulk_create(rows, ignore_conflicts=True)
