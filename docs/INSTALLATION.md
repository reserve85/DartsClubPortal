# Installation & configuration

The portal is one Docker container with an SQLite database. Everything it
stores (database, player pictures, club logo, safety copies) lives in one
data folder, so a NAS such as Synology or QNAP is enough.

## Install

### Portainer (recommended for a NAS)

1. *Stacks → Add stack*, paste [`portainer_compose.yaml`](../portainer_compose.yaml).
2. Set at least:
   - `DJANGO_SECRET_KEY`: a long random string
     (`python -c "import secrets; print(secrets.token_urlsafe(50))"`),
   - `DJANGO_ALLOWED_HOSTS`: your host name(s), **without** `https://`,
   - `DJANGO_SUPERUSER_EMAIL` / `DJANGO_SUPERUSER_PASSWORD`: the first admin,
   - the data folder on the left of `:/app/data`, e.g.
     `/volume1/docker/darts/data:/app/data`.
3. Deploy and open `http://<host>:8000`; log in with the admin e-mail.

### docker compose

```bash
git clone https://github.com/reserve85/DartsClubPortal.git && cd DartsClubPortal
cp .env.example .env        # set DJANGO_SECRET_KEY + DJANGO_SUPERUSER_* at least
docker compose up -d --build
```

### Data folder and file permissions

The container starts as root only to hand the data folder to `PUID`/`PGID`
and then runs unprivileged as that user. Set both to the owner of the data
folder on the host (`stat -c '%u %g' <data folder>`, e.g. `1026 100` for the
first user on a Synology).

## Update

Pull `ghcr.io/reserve85/darts_club_portal:latest` (Portainer: *Recreate* with
*Re-pull image*) or `docker compose pull && docker compose up -d`. Database
migrations run automatically at start. Download a backup first
(*Administration → Import & Export*).

## HTTPS behind a reverse proxy

Behind Synology DSM, nginx, Traefik, … terminate TLS at the proxy and set:

```
DJANGO_ALLOWED_HOSTS=darts.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://darts.example.com
DJANGO_SECURE_PROXY_SSL_HEADER=true
DJANGO_SECURE_SSL_REDIRECT=true
PUBLIC_SITE_URL=https://darts.example.com
```

Raise `DJANGO_SECURE_HSTS_SECONDS` (e.g. `31536000`) once HTTPS works for
good. If the proxy limits upload sizes, allow a few megabytes for pictures and
more for restoring backups.

## Backups

*Administration → Import & Export* downloads a **full backup** (database,
player pictures, club logo) as one ZIP and restores it again. Before a
restore the current state is saved to `BACKUP_DIR` (last 5 copies). You can
also copy the data folder itself while the container is stopped.

## Configuration reference

Every option is also documented inline in
[`portainer_compose.yaml`](../portainer_compose.yaml) and
[`.env.example`](../.env.example).

### Portal

| Variable | Default | Meaning |
|---|---|---|
| `SITE_NAME` | `Darts Club Portal` | Name in the header, page titles and mails |
| `MODULES` | `elo,penalty` | Enabled modules (`elo`, `penalty`) |
| `DEFAULT_START_PAGE` | `elo` | `elo`, `penalty` or `overview` |
| `PUBLIC_SITE_URL` | – | Address used in mail links and QR codes |
| `DJANGO_LANGUAGE_CODE` | `de` | Default language (`de`, `en`) |
| `DJANGO_TIME_ZONE` | `Europe/Berlin` | IANA time zone |

### Elo

| Variable | Default | Meaning |
|---|---|---|
| `ELO_DEFAULT_ELO` | `1200` | Start Elo of new players |
| `ELO_K_FACTOR` | `32` | How fast ratings move |
| `ELO_INACTIVITY_MONTHS` | `3` | Months without a match until a player counts as inactive |
| `ELO_BEST_OF_LEGS` | `5` | Default match format |
| `ELO_HIGH_FINISH_MIN` / `_MAX` | `100` / `170` | Range of a high finish |
| `ELO_LOW_DARTS_MIN` / `_MAX` | `9` / `21` | Range of "low darts" |
| `ELO_LEGACY_JWT_SECRET` | – | Accept QR codes of the old Elo system (leave empty otherwise) |
| `ELO_LEGACY_QR_LOGIN` | `true` | Accept the oldest Elo QR codes (`false` once replaced) |

### Security and storage

| Variable | Default | Meaning |
|---|---|---|
| `DJANGO_SECRET_KEY` | – | **Required**, long random string |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Host names, comma separated |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | – | `https://…` origins behind a proxy |
| `DJANGO_SECURE_PROXY_SSL_HEADER` | `false` | Trust `X-Forwarded-Proto` of the proxy |
| `DJANGO_SECURE_SSL_REDIRECT` | `false` | Redirect to HTTPS, secure cookies |
| `DJANGO_SECURE_HSTS_SECONDS` | `0` | HSTS max-age |
| `ALLAUTH_TRUSTED_PROXY_COUNT` | `0` | Number of proxies in front (real client IP for rate limits) |
| `SQLITE_PATH` | `data/db.sqlite3` | Database file |
| `MEDIA_ROOT` | `data/media` | Player pictures and club logo |
| `BACKUP_DIR` | `data/backups` | Safety copies before a restore |
| `PUID` / `PGID` | `1000` / `1000` | Owner of the data folder |
| `DJANGO_SUPERUSER_EMAIL` / `_PASSWORD` | – | First admin (only created if missing) |

### Mail

| Variable | Default | Meaning |
|---|---|---|
| `EMAIL_HOST`, `EMAIL_PORT` | –, `587` | SMTP server; empty = mails are only logged |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | – | SMTP login |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | `true` / `false` | STARTTLS (587) or SSL (465) |
| `DEFAULT_FROM_EMAIL`, `SUPPORT_EMAIL` | – | Sender and support address |
| `ACCOUNT_EMAIL_VERIFICATION` | `mandatory` | `mandatory`, `optional`, `none` |
| `NOTIFICATION_QUIET_HOURS` | – | e.g. `22:00-07:00`: no single mails at night |
| `INVITE_EXPIRE_DAYS` | `14` | Validity of invitation links |

### Imprint and privacy policy

`CONTACT_COMPANY`, `CONTACT_NAME`, `CONTACT_STREET`, `CONTACT_CITY`,
`CONTACT_EMAIL` fill the imprint and privacy pages (required in Germany for a
public site).
