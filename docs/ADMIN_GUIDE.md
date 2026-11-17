# Admin guide

What the club's admins do in the portal, from the first login to the
monthly routine. Every member can also open *Who may do what?* in the user
menu - it explains the rights in plain words.

## Roles and rights

| Role / assignment | What it means |
|---|---|
| **System** | The operator account from `DJANGO_SUPERUSER_EMAIL`; can do everything. |
| **Admin** | Rights in one or more *admin areas*: **Elo** (matches, Elo players, recalculation, CSV), **Penalty** (seasons, teams, matchdays and penalties of every team, catalog, cash box), **Portal** (accounts, invitations, approvals, rights, audit log, backup, club logo). |
| **User** | Enters Elo matches, sees the financial overview, own penalties and settings. |
| **Club account** | A shared login (e.g. the tablet at the board). The only kind of account a QR code can log in. Never an admin, never linked to a player. |
| **Captain** *(assignment)* | Manages matchdays and penalties of their own team. |
| **Cashier** *(assignment)* | Records payments and payouts of their team. |

Each account also has module access (Elo / Penalty), so a person can use the
Elo ranking only, for example.

## First steps

1. Log in with the admin from `DJANGO_SUPERUSER_EMAIL`.
2. *Administration → Seasons*: create the current season.
3. *Penalty → Teams & Players*: create the teams, assign captain and cashier.
4. *Penalty → Penalty catalog*: penalty types and fees per team.
5. *Administration → Club logo*: upload the logo (light and dark version).
6. *Administration → Members*: add the people (next section).

## Members

*Administration → Members* lists every person of the club, with or without
a login, and is the quickest way to manage them:

- **Quick add:** type a name and press Enter; several at once, one per line.
  The team of the season and the Elo start are filled in.
- **Invite:** the row button sends an invitation mail; the account is linked
  to the member when the invitation is accepted.
- **+ Elo:** puts a member into the Elo ranking with the default start Elo.
- **Member page:** name and active flag, teams of the season, Elo (start Elo,
  entry date, disable), account (invite, link an existing account, unlink),
  picture.
- Filters show who still needs an account or the Elo ranking.

Members can also register themselves; they then wait for approval under
*Konten & Rechte → Approvals*.

## Club account and QR poster

1. *Konten & Rechte → Edit*: tick **Club account** for the shared login.
2. Use **QR** in the account list: the page is an A4 poster with logo,
   headline, a large QR code and the portal address - print it for the board.
3. Changing the club account's password makes every printed code invalid.

## Everyday tasks

- **Matchday:** *Penalty → Matchdays → New*, choose the participants, add
  penalties (group penalties such as "180 → everybody else pays" included).
- **Payments:** the cashier records payments and payouts under *Cash box*;
  members get a receipt by mail if they want.
- **Elo corrections:** edit or delete a match; the history is recalculated.
- **Mails:** members choose per mail type (each one or a daily summary) in
  *Settings*; the monthly Elo report goes out on the 1st.

## Backup and restore

*Administration → Import & Export*:

- **Full backup (ZIP):** database, player pictures and club logo.
- **Restore:** upload a full backup or a database, confirm with your
  password. A safety copy of the current state is saved first
  (`data/backups`, last 5). Older backups are migrated automatically.
- **CSV:** Elo ranking, matches and players for Excel (Elo admins).

Download a backup before every update.

## Audit log

*Administration → Audit* records every change to money, penalties, matches,
accounts, rights, exports and restores - who, when and what.
