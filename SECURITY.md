# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Report them
privately through a
[GitHub security advisory](https://github.com/reserve85/DartsClubPortal/security/advisories/new).

Include what you found, how to reproduce it and which version you use
(shown in the footer of the portal). You will get an answer as soon as
possible; fixes are released as a new version and mentioned in the release
notes once users had a chance to update.

## Supported versions

Only the latest release receives security fixes. Update by pulling
`ghcr.io/reserve85/darts_club_portal:latest`.

## Running it safely

- Set a long random `DJANGO_SECRET_KEY` and never commit your compose file
  with real passwords.
- Serve the portal over HTTPS (see [docs/INSTALLATION.md](docs/INSTALLATION.md)).
- Print QR codes only for the club account; change its password if a code
  gets lost.
- Download a backup regularly (*Administration → Import & Export*).
