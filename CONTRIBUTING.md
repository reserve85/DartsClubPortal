# Contributing

Thanks for helping! Bug reports, ideas and pull requests are welcome.

- **Bugs and ideas:** open an issue with what you expected, what happened and
  the version from the footer of the portal.
- **Security problems:** please report privately, see [SECURITY.md](SECURITY.md).
- **Pull requests:** keep them focused on one topic and include tests.

## Stack

Django 5.2 · django-allauth · React 19 + Mantine 9 via Inertia · Vite ·
TypeScript · SQLite · pytest · ruff.

```
app/          Django apps: accounts, players, teams, matchdays, penalties,
              elo, notifications, dashboard, backup, core
frontend/     React pages (frontend/src/pages) and components
locale/       German and English translations (.po)
tests/        pytest suite
```

## Local setup

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py bootstrap                         # admin from DJANGO_SUPERUSER_*
python manage.py seed_demo                         # optional: invented demo data
cd frontend && npm ci && npm run build && cd ..
python manage.py runserver
```

For frontend work run `npm run dev` in `frontend/` and set `VITE_DEV_MODE=true`.

## Checks (the same as CI)

```bash
ruff check . && ruff format --check .
cd frontend && npm run build && cd ..             # type check + build
python manage.py sync_frontend_i18n               # after changing texts in the frontend
python manage.py compilemessages
pytest
```

## Conventions

- Code, comments, commit messages and docs are **English**; the user
  interface is German and English (`locale/de`, `locale/en`).
- New user-facing texts: wrap them in `_()` / `t()` and add the German
  translation to `locale/de/LC_MESSAGES/django.po`.
- Never commit real data (databases, compose files with passwords, member
  names). Use `seed_demo` for screenshots.

## Releases

A GitHub release `vX.Y.Z` builds and publishes the Docker image
`ghcr.io/reserve85/darts_club_portal` (`X.Y.Z` and `latest`).
