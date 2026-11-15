# DartsClubPortal – one app for the club

**Goal:** a single club portal in **one container** with one account, one
design and one language setting. The Elo ranking and the penalty management
are **modules** that are switched on or off by configuration: Elo only,
penalty only, or both.

The portal grows out of **DartsPenaltySystem** (this repository is a fork with
its full Git history); **EloRankingSystem** is ported in as a module. Both old
projects keep running unchanged until the club switches over, and **both of
their databases can be imported completely**.

## Decisions

| Topic | Decision |
|---|---|
| Container | **One**: a single image for every combination, modules via `MODULES=elo,penalty` |
| Base | Django 5.2 from DartsPenaltySystem (accounts, approval, invitations, e-mails, seasons, audit) |
| Accounts | One account table; portal admin = admin in every module |
| People | **One** player record per person; Elo and penalty data hang off it |
| Language | Technical names, settings, docs and commits are **English**; the UI is German (default) + English via Django translations |
| Design | One base template in the new design (gradient hero, initials avatars, cards, toasts), mobile first |
| Import | Elo database **and** penalty database importable: admin upload and CLI, each with a dry-run preview |
| Old projects | Stay deployable until the switch; afterwards only the portal is maintained and the old repositories are archived |

---

## 1. Structure

```
DartsClubPortal (Django, 1 container, 1 SQLite database, 1 volume)
├── core        settings, module switch, menu, audit, legal pages
├── accounts    accounts, login, approval, invitations, profile (language, theme)
├── players     people (shared by all modules)
├── penalty     the existing penalty apps (teams, matchdays, penalties, dashboard, seasons …)
├── elo         NEW: matches, Elo calculation, ranking, statistics, head-to-head,
│               export (PDF/CSV), QR login
├── portal      "My overview": Elo tile + penalty tile
└── importer    imports of the Elo and the penalty database
```

**Module switch (`MODULES`)**
- A disabled module is invisible: no menu entry, no pages, no API, no tile.
  Its tables and data stay and are back when it is switched on again.
- The base (accounts, people, settings, audit) is always on.
- One image for every combination – no special builds.

**People**
- `players.Player` (name, status) is the shared person.
- The Elo module adds an `EloProfile` (1:1): start Elo, current Elo, entry date,
  Elo status (active/disabled).
- Teams, seasons and penalties keep pointing at the same player.
- A person can be active in one module and absent from the other.

## 2. Elo as a module

- **Port the logic 1:1:** Elo formula, timeline recalculation, ranking (full
  field, inactivity as of the period end), best rank, all-time high,
  head-to-head and the plausibility checks. Only the queries move from
  SQLAlchemy to the Django ORM.
- **Port the tests:** The Elo tests for calculation, recalculation, ranking and
  statistics move to Django, so no fixed rule is lost.
- **Keep the JSON API:** With django-ninja (pydantic schemas, FastAPI-like)
  paths and response formats stay the same, so the new UI (dashboard,
  statistics, head-to-head, admin) carries over largely unchanged.
- **Permissions:**
  - Members enter matches and see ranking and statistics.
  - Admins manage matches, players, exports and backups.
- **QR login** for a shared club account (e.g. a tablet in the club house)
  stays, with the token in the QR code as in Elo v1.0.39.

## 3. Importing the existing databases

Both imports work the same way: **choose file → preview → match people →
import → verification report**.

- **Where:** in the admin area ("Administration → Import", upload of the SQLite
  file) and on the command line (`manage.py import_elo <file>`,
  `manage.py import_penalty <file>`).
- **Dry run:** Every import can run as a preview first. It writes nothing and
  lists what would be created, matched or skipped.
- **All or nothing:** An import runs in **one transaction**; on any error
  nothing is taken over.
- **No duplicates:** Every imported record remembers its origin (source + id),
  so running the same import twice creates nothing twice.
- **Backup:** Before every import the portal database is backed up
  automatically.

### 3.1 Penalty database (DartsPenaltySystem)

- **Switch-over (normal case):** The portal shares the migrations of
  DartsPenaltySystem, so an existing penalty database can be used as the portal
  database directly (keep the volume, swap the container). All accounts,
  passwords, teams, seasons, penalties, payments and audit entries stay.
- **Import into an existing portal:** If Elo was imported first,
  `import_penalty` takes over accounts, players, teams, seasons, matchdays,
  catalog, penalties, payments, cash-box history and audit.
  - People are merged through the matching step.
  - Accounts are merged by e-mail address.
- **Supported versions:** every version the current migrations know. Older
  files are migrated on a copy first.

### 3.2 Elo database (EloRankingSystem)

| Elo data | Target in the portal |
|---|---|
| Players | person (matched or new) + `EloProfile` (start Elo, entry date, status) |
| Matches | Elo matches incl. score, format, K-factor, statistics and the **stored Elo snapshots** |
| Disable periods | taken over |
| Users | accounts (see below) |
| Club logo | taken over if the portal has none |
| Audit log | taken over, marked with origin "elo" |

- **Matching people:** For every Elo player the preview proposes an existing
  person by name (case, umlauts and spaces ignored). You confirm, change or
  create a new one.
- **Accounts:**
  - Elo accounts keep their **password**: Elo stores Argon2, which Django
    verifies directly. It is upgraded to Django's default hasher on the first
    login.
  - Elo signs in with a **user name**, the portal with an **e-mail address**.
    For every Elo account you choose in the preview:
    - attach it to an existing portal account
    - create it as an account with e-mail
    - take it over as a **club account** (user-name login, e.g. for QR codes)
    - skip it
  - Elo ADMIN becomes portal admin; the SYSTEM account is not taken over.
- **Verification report:** After the import the Elo timeline is recalculated
  from the imported matches and compared with the stored snapshots.
  Differences are reported and can be fixed with "Recalculate".
- **Supported versions:** EloRankingSystem v1.0.39 or newer. Older databases
  are first upgraded by starting the old app once; the import checks this and
  says so clearly.

## 4. Design and usability

- **Base template:** One base template for all pages in the new design from
  Elo v1.0.41: gradient hero, initials avatars, chips, tiles, card lists on
  phones, toasts and busy buttons. Technology: Bootstrap 5.3, with the
  Tabler-style elements from Elo rebuilt on it.
- **Menu:** Overview · Ranking · Penalties · Administration · Profile. It shows
  only the enabled modules.
- **Penalty pages:** moved onto the same components.
- **Dark mode and language:** per account, as today in DartsPenaltySystem.

## 5. Roll-out plan

| Phase | Content | Result |
|---|---|---|
| **0** | Base: fork, name/branding, module switch `MODULES`, menu, tests green | ✅ portal = today's penalty app, modules switchable |
| **1** | Design: new base template + UI kit, penalty pages restyled, screenshots | target design in place |
| **2** | Elo core: models, Elo calculation, recalculation, ranking, statistics, head-to-head + ported tests | calculation identical to Elo |
| **3** | Elo UI + API: dashboard, match entry, statistics, head-to-head, administration, PDF/CSV, QR login, German/English | Elo module usable |
| **4** | Import: `import_elo` + `import_penalty` with preview, matching, transaction, verification report; admin upload | data of both systems importable |
| **5** | "My overview" (Elo + penalty), club accounts, role polish | portal start page |
| **6** | One image, Compose/Portainer example, switch-over guide, end-to-end test with real copies of both databases | ready to switch |

Every phase ends with tests and screenshots for approval.

## 6. Switch-over (short)

1. Back up both old systems (Elo: "System → Download Backup", penalty: copy
   the volume).
2. Start the portal container on the **penalty volume**; the database is
   taken over and migrated.
3. Enable Elo in the portal and **import the Elo database**: preview,
   matching, import, verification report.
4. Check everything, then stop the old containers.

## 7. Earlier work

- Elo `feat/ui-redesign`: the design becomes the portal's template; it can
  still be released as Elo v1.0.41 independently.
- Elo `feat/portal-integration` (SSO add-in for three containers): not needed
  for this plan; stays unreleased.
- All Elo fixes and rules (ranking, validation, security) are the basis of
  the port.
