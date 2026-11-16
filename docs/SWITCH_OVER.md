# Switching over from DartsPenaltySystem + EloRankingSystem

One container replaces both old systems. Both old databases are imported;
the old containers keep running untouched until you are happy.

## 1. Prepare

1. Back up both systems:
   - penalty: copy `db.sqlite3` from its data volume,
   - Elo: *Admin → Backup* (zip with `database.db` and the logos).
2. Note the `JWT_SECRET` of the Elo installation if printed QR codes are in
   use (`ELO_LEGACY_JWT_SECRET`).

## 2. Start the portal

Deploy `portainer_compose.yaml` (image `ghcr.io/reserve85/darts_club_portal`)
with a new, empty data volume. Important variables:

| Variable | Value |
|---|---|
| `MODULES` | `elo,penalty` |
| `DEFAULT_START_PAGE` | `elo` |
| `PUBLIC_SITE_URL` | public address (links in e-mails) |
| `ELO_LEGACY_JWT_SECRET` | `JWT_SECRET` of the old Elo system |
| SMTP block | as in the penalty system |

Log in with the admin account from `DJANGO_SUPERUSER_EMAIL`.

## 3. Import (Administration → Import)

Order matters: **penalty first** (it has the e-mail addresses), **then Elo**.

1. *Penalty system (db.sqlite3)* → **Show preview** → check → **Import now**.
   Accounts, teams, seasons, players, matchdays, penalties, payments and the
   audit log are copied.
2. *Elo system (database.db)* → **Show preview**.
   - Players are matched by name to the people from step 1 (the preview lists
     every match; new names are created).
   - Elo logins have no e-mail: link each admin login (e.g. `Dennis`) to the
     person's portal account; leave the club account (e.g. `Wildboars`) on
     *create a new account* – it becomes an Elo-only account.
   - Every match is recalculated and compared with the old values; all checks
     must be green.
   → **Import now**.

Command line alternative (inside the container):

```
python manage.py import_penalty /app/data/old/db.sqlite3 --dry-run
python manage.py import_penalty /app/data/old/db.sqlite3
python manage.py import_elo /app/data/old/database.db --dry-run --map-account Dennis=dennis@example.com
python manage.py import_elo /app/data/old/database.db --map-account Dennis=dennis@example.com
```

## 4. After the import

- Old passwords keep working (Elo accounts keep their argon2 hashes).
- Old printed QR codes keep working on the **same address** (point the old
  host name to the portal). Print new ones under *Administration → Users →
  QR* and switch `ELO_LEGACY_QR_LOGIN=false` once all are replaced.
- Check *Administration → Users*: module access (Elo / Penalty) per account.
- Members choose their start page and e-mails under *Settings*.

## 5. Rehearsal result (copies of the live databases, 16.11.2026)

- penalty: 25 of 25 penalties, 42 of 42 matchdays, 6 accounts copied,
- Elo: 35 players (34 matched to penalty people), 479 matches,
  recalculation identical to the old system (largest difference 0.0000).
