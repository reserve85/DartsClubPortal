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
     *create a new account* – it becomes a User account (enters Elo matches, sees the penalties read-only).
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

## Environment variables of the old containers

**DartsPenaltySystem:** every variable keeps its name and meaning in the
portal – the old `environment:` block can be copied as it is.

**EloRankingSystem:** the old names are still read (the portal name wins
when both are set), so the old block can be copied too:

| Old Elo container | Portal name | Note |
|---|---|---|
| `DEFAULT_ELO` | `ELO_DEFAULT_ELO` | |
| `K_FACTOR` | `ELO_K_FACTOR` | |
| `INACTIVITY_MONTHS` | `ELO_INACTIVITY_MONTHS` | |
| `HIGH_FINISH_MIN` / `_MAX` | `ELO_HIGH_FINISH_MIN` / `_MAX` | |
| `LOW_DARTS_MIN` / `_MAX` | `ELO_LOW_DARTS_MIN` / `_MAX` | |
| `BEST_OF_LEGS` | `ELO_BEST_OF_LEGS` | |
| `JWT_SECRET` | `ELO_LEGACY_JWT_SECRET` | keeps old printed QR codes working |
| `LEGACY_QR_LOGIN_ENABLED` | `ELO_LEGACY_QR_LOGIN` | |
| `APP_BASE_URL` | `PUBLIC_SITE_URL` | links in e-mails and QR codes |
| `CLUB_NAME` | `SITE_NAME` | |
| `TIMEZONE` | `DJANGO_TIME_ZONE` | |
| `LOG_LEVEL` | `DJANGO_LOG_LEVEL` | |
| `APP_DEBUG` | `DJANGO_DEBUG` | |
| `COOKIE_SECURE` | `DJANGO_SESSION_COOKIE_SECURE` | |
| `CONTACT_*` | `CONTACT_*` | same names |
| `APP_VERSION`, `GIT_COMMIT`, `BUILD_DATE` | same | baked into the image |

Not needed any more (the portal solves it differently):
`SYSTEM_USER_USERNAME` / `SYSTEM_USER_PASSWORD` → the admin is
`DJANGO_SUPERUSER_EMAIL` / `DJANGO_SUPERUSER_PASSWORD` (login by e-mail);
`DATABASE_URL`, `DATA_DIR`, `UPLOAD_DIR` → `SQLITE_PATH` / `MEDIA_ROOT`
in the `/app/data` volume; `JWT_ALGORITHM`, `ACCESS_TOKEN_LIFETIME_MINUTES`,
`COOKIE_HTTPONLY`, `COOKIE_SAMESITE`, `CSRF_ENABLED`, `RATE_LIMIT_ENABLED`
→ session login with secure defaults, CSRF and rate limits are always on;
`TRUSTED_PROXIES` → `ALLAUTH_TRUSTED_PROXY_COUNT` (number of proxies) and
`DJANGO_SECURE_PROXY_SSL_HEADER`; `DATE_FORMAT` → follows the language;
`APP_NAME`, `APP_ENV`, `CONFIG_PATH`, `AUDIT_RETENTION_DAYS` → not used
(the audit log is kept completely). Settings that lived only in the old
`config.yaml` must be written as environment variables.
