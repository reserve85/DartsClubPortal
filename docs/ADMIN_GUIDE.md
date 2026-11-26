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

**Forgotten password:** members reset it themselves with *Forgot password*
on the login page (needs SMTP). When that is not possible, a portal admin
sets a new one under *Konten & Rechte → Edit → Set password* - the page asks
before it changes anything, and the account is signed out everywhere.

## Club account and QR poster

1. *Konten & Rechte → Edit*: tick **Club account** for the shared login.
2. Use **QR** in the account list: the page is an A4 poster with logo,
   headline, a large QR code and the portal address - print it for the board.
3. Only portal admins set the club account's password: *Konten & Rechte →
   Edit → Set password*. The club account cannot change its own password or
   e-mail, and "forgot password" skips it - nobody at the tablet can lock
   the club out.
4. A new password makes every printed code invalid and signs the tablet
   out: print the poster again.

## nuLiga: matchdays imported automatically

1. Open the team in nuLiga (league → group → click the team) and copy the
   address of that page.
2. *Penalty → Seasons → Edit*: paste it next to the team under **nuLiga** and
   save. The matchdays of the season are imported right away - date, time,
   home or away, opponent and the venue address. Matchdays you entered by
   hand are linked instead of doubled (same day, or same opponent when the
   match was moved).
3. From then on the portal checks nuLiga every day from 06:00. The captain
   gets a message (in the app and by e-mail) when a matchday is added, moved,
   changes home/away or the venue, or leaves the schedule. A matchday that
   left the schedule is only marked - delete it yourself if it is cancelled.
   If nuLiga cannot be reached, the import tries again every hour (the
   matchday page shows it); after 24 failures in a row the system account
   gets a message, and the import goes back to once a day.
4. *Matchdays → Sync with nuLiga now* imports at once (admins: every team,
   captains: their team). The link belongs to the season: paste the new
   team page when the next season starts.
5. **Different agreement with the opponent** (another time, a day earlier):
   edit the matchday and tick **Manage by hand**. nuLiga no longer changes
   it; when nuLiga changes something there, the captain is told once.
   Untick it to follow nuLiga again. A deleted matchday is not imported
   again.
6. **Subscribe to calendar** (matchdays page and overview): the matchdays of
   a team - or of every team - in the phone's calendar, kept up to date by
   the portal (hand-made changes and cancellations included).

The overview shows the **next matchdays** of every team - the next two
weeks, at least the next one - with the own teams first.

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
