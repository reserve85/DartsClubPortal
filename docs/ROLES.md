# Roles and permissions

Three roles (Django groups) plus per-module access per account.

| | Admin | Captain | Player |
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

Captains are deliberately **not** admins: everything they can change is
limited to the team they lead (`User.team`).

## Module access

Every account has `Elo access` and `Penalty access` (Administration → Users).
A module the account may not use disappears from the menu and its pages
answer 403. Admins always have every module the installation runs
(`MODULES`).

Typical accounts:

- **Member** – Player role, both modules.
- **Elo-only** – Player role, only Elo access (e.g. the shared club account
  at the board, logged in by QR code, or guests who only play Elo).
- **Captain** – Captain role with a team, usually both modules.

## Start page

`/` opens the user's start page: Elo ranking (club default,
`DEFAULT_START_PAGE`), financial overview or "My overview" – each user can
choose it in the settings.
