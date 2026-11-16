# Roles and permissions

Roles: **System** (the operator account from `DJANGO_SUPERUSER_EMAIL`),
**Admin** and **User**. *Captain of a team* (Administration → Users → team)
and *Cashier of a team* (Penalty → Cash box) are **assignments** any account
can hold – an Admin can be a captain too. Plus per-module access per account.

| | Admin | Captain (any role) | User |
|---|---|---|---|
| **Elo** – ranking, statistics, head-to-head, matches | ✓ | ✓ | ✓ |
| **Elo** – enter a match | ✓ | ✓ | ✓ |
| **Elo** – edit / delete matches | ✓ | – | – |
| **Elo** – players, recalculation, exports | ✓ | – | – |
| **Penalty** – own balance, financial overview | ✓ | ✓ | ✓ |
| **Penalty** – matchdays and penalties | all teams | **own team** (others read-only) | – |
| **Penalty** – players | all | **own team's** players | – |
| **Penalty** – catalog | everything | **own team's** fee and active flag; new items start active only for the own team | – |
| **Penalty** – delete catalog items, change the shared name / default fee | ✓ | – | – |
| **Penalty** – cash box (assign cashier) | all teams | own team | – |
| **Penalty** – payments | the team's cashier | the team's cashier | – |
| Seasons, users, invitations, approvals | ✓ | – | – |
| Audit log, import | ✓ | – | – |
| QR codes for shared accounts | ✓ | – | – |

A captain who is not an admin can only change the team they lead
(`User.team`); an admin who is also captain keeps all admin rights.

## Module access

Every account has `Elo access` and `Penalty access` (Administration → Users).
A module the account may not use disappears from the menu and its pages
answer 403. Admins always have every module the installation runs
(`MODULES`).

Typical accounts:

- **Member** – User role, both modules.
- **Elo-only** – User role, only Elo access (e.g. the shared club account
  at the board, logged in by QR code, or guests who only play Elo).
- **Captain** – any role with a team assigned.

## Start page

`/` opens the user's start page: Elo ranking (club default,
`DEFAULT_START_PAGE`), financial overview or "My overview" – each user can
choose it in the settings.
