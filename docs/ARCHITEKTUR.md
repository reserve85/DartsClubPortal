# ClubPortal – eine App für den Verein

**Ziel:** Ein einziges Vereinsportal in **einem Container** mit einem Konto, einem
Design und einer Sprache. Die Elo-Rangliste und die Strafenverwaltung sind
**Module**, die per Einstellung an- oder ausgeschaltet werden: nur Elo, nur
Strafen oder beides.

Das Portal entsteht aus **DartsPenaltySystem** (dieses Repo ist ein Abzweig mit
voller Git-Historie). EloRankingSystem wird als Modul **hineinportiert**. Beide
alten Projekte laufen unverändert weiter, bis der Verein umstellt. Ihre
**Datenbanken lassen sich vollständig importieren**.

## Festgelegte Entscheidungen

| Thema | Entscheidung |
|---|---|
| Container | **Einer**: ein Image für alle, Module per `MODULES=elo,strafen` |
| Basis | Django 5.2 aus DartsPenaltySystem (Konten, Freigabe, Einladungen, E-Mails, Saisons, Audit) |
| Benutzerkonten | Eine Kontotabelle; Portal-Admin = Admin in allen Modulen |
| Personen | **Ein** Spieler-Datensatz pro Person; Elo- und Strafen-Daten hängen daran |
| Sprache | Deutsch (Standard) + Englisch für alles (Django-Übersetzungen) |
| Design | Eine Basisvorlage im neuen Design (Farbverlauf, Initialen-Avatare, Karten, Toasts), Mobil zuerst |
| Import | Elo-Datenbank **und** Strafen-Datenbank importierbar: im Admin-Bereich per Upload und per Kommandozeile, jeweils mit Vorschau |
| Alte Projekte | Bleiben eigenständig lauffähig, bis umgestellt ist; danach nur noch das Portal |

---

## 1. Aufbau

```
ClubPortal (Django, 1 Container, 1 SQLite-Datenbank, 1 Volume)
├── core        Einstellungen, Module an/aus, Menü, Audit, Saisons, Rechtliches
├── accounts    Konten, Login, Freigabe, Einladungen, Profil (Sprache, Design)
├── players     Personen (gemeinsam für alle Module)
├── strafen     bisherige Strafen-Apps (teams, matchdays, penalties, dashboard …)
├── elo         NEU: Matches, Elo-Berechnung, Rangliste, Statistik, Head-to-Head,
│               Export (PDF/CSV), QR-Login
├── portal      „Meine Übersicht“: Elo-Kachel + Strafen-Kachel
└── importer    Import der Elo- und der Strafen-Datenbank
```

**Module an/aus (`MODULES`)**
- Ein abgeschaltetes Modul ist unsichtbar: kein Menüpunkt, keine Seiten,
  keine API, keine Kachel. Seine Tabellen und Daten bleiben erhalten; beim
  Einschalten ist alles wieder da.
- Die Basis (Konten, Personen, Einstellungen, Audit) ist immer aktiv.
- Kein Neubau nötig: dasselbe Image für jede Kombination.

**Personen**
- `players.Player` (Name, Status) ist die gemeinsame Person.
- Das Elo-Modul ergänzt ein `EloProfile` (1:1): Start-Elo, aktuelle Elo,
  Eintrittsdatum, Elo-Status (aktiv/gesperrt).
- Teams, Saisons und Strafen hängen wie bisher am selben Spieler.
- Eine Person kann in einem Modul aktiv und im anderen nicht vorhanden sein.

## 2. Elo als Modul

- **Rechenlogik 1:1 übernehmen:** Elo-Formel, Zeitachsen-Neuberechnung,
  Rangliste (volles Feld, Inaktivität zum Stichtag), Best Rank, All-Time-High,
  Head-to-Head, Plausibilitätsprüfungen. Nur die Datenbankabfragen wechseln
  von SQLAlchemy auf Django.
- **Tests mitnehmen:** Die Elo-Tests (Rechnung, Neuberechnung, Rangliste,
  Statistik) werden auf Django portiert, damit keine bereits behobene Regel
  verloren geht.
- **JSON-Schnittstelle unverändert:** Mit django-ninja (pydantic-Schemas wie
  bei FastAPI) bleiben Pfade und Antwortformate gleich. Die neue Oberfläche
  (Dashboard, Statistik, Head-to-Head, Admin) lässt sich dadurch weitgehend
  übernehmen.
- **Rechte:**
  - Mitglieder dürfen Matches eintragen und Ranglisten und Statistiken sehen.
  - Admins verwalten Matches, Spieler, Export und Backup.
- **QR-Login** für ein gemeinsames Vereinskonto (z. B. Tablet im Vereinsheim)
  bleibt erhalten: Token im QR-Code, wie in Elo v1.0.39.

## 3. Import der bestehenden Datenbanken

Beide Importe laufen gleich ab: **Datei wählen → Vorschau → Personen zuordnen →
Import → Prüfbericht**.

- **Wo:** im Admin-Bereich („Verwaltung → Import“, Upload der SQLite-Datei)
  und als Befehl (`manage.py import_elo <datei>`,
  `manage.py import_strafen <datei>`).
- **Probelauf:** Jeder Import kann vorher nur angezeigt werden. Er schreibt
  dann nichts, sondern listet, was angelegt, zugeordnet oder übersprungen
  würde.
- **Alles oder nichts:** Ein Import läuft in **einer Transaktion**; bei einem
  Fehler wird nichts übernommen.
- **Doppelimport ausgeschlossen:** Jeder übernommene Datensatz merkt sich
  seine Herkunft (Quelle + ID). Derselbe Import ein zweites Mal legt nichts
  doppelt an.
- **Sicherung:** Vor jedem Import wird automatisch ein Backup der
  Portal-Datenbank erstellt.

### 3.1 Strafen-Datenbank (DartsPenaltySystem)

- **Umstieg (Normalfall):** Das Portal nutzt dieselben Migrationen wie
  DartsPenaltySystem. Die bestehende Strafen-Datenbank kann deshalb direkt als
  Portal-Datenbank weiterverwendet werden (Volume übernehmen, Container
  tauschen). Alle Konten, Passwörter, Teams, Saisons, Strafen, Zahlungen und
  Audit-Einträge bleiben erhalten.
- **Import in ein bestehendes Portal:** Wurde zuerst Elo importiert, übernimmt
  `import_strafen` Konten, Spieler, Teams, Saisons, Spieltage, Katalog,
  Strafen, Zahlungen, Kassenhistorie und Audit.
  - Personen werden über die Zuordnung zusammengeführt.
  - Konten werden über die E-Mail-Adresse zusammengeführt.
- **Unterstützte Stände:** Unterstützt werden alle Stände, die die aktuellen
  Migrationen kennen. Ältere Dateien werden vor dem Import automatisch
  migriert (auf einer Kopie).

### 3.2 Elo-Datenbank (EloRankingSystem)

| Elo-Daten | Ziel im Portal |
|---|---|
| Spieler | Person (zugeordnet oder neu) + `EloProfile` (Start-Elo, Eintrittsdatum, Status) |
| Matches | Elo-Matches inkl. Ergebnis, Format, K-Faktor, Statistik und **gespeicherten Elo-Ständen** |
| Sperrzeiträume | übernommen |
| Benutzer | Konten (siehe unten) |
| Vereinslogo | übernommen, sofern das Portal noch keines hat |
| Audit-Log | übernommen, als Herkunft „Elo“ markiert |

- **Personen-Zuordnung:** Für jeden Elo-Spieler schlägt die Vorschau eine
  vorhandene Person per Namensabgleich vor (Groß-/Kleinschreibung, Umlaute,
  Leerzeichen egal). Du bestätigst, änderst oder lässt neu anlegen.
- **Konten:**
  - Elo-Konten behalten ihr **Passwort**: Elo speichert Argon2, Django prüft
    Argon2 direkt. Beim ersten Login wird auf das Django-Standardverfahren
    umgestellt.
  - Elo meldet mit **Benutzernamen** an, das Portal mit **E-Mail**. Zu jedem
    Elo-Konto wählst du in der Vorschau:
    - an ein bestehendes Portal-Konto hängen
    - als Konto mit E-Mail neu anlegen
    - als **Vereinskonto** (Benutzername-Login, z. B. für QR-Codes) übernehmen
    - weglassen
  - Elo-ADMIN wird Portal-Admin. Das SYSTEM-Konto wird nicht übernommen.
- **Prüfbericht nach dem Import:** Die Elo-Zeitachse wird aus den importierten
  Matches neu berechnet und mit den gespeicherten Ständen verglichen.
  Abweichungen werden gemeldet; auf Wunsch wird mit „Neuberechnen“
  bereinigt.
- **Unterstützte Stände:** EloRankingSystem ab v1.0.39. Ältere Datenbanken
  zuerst mit der alten App auf v1.0.39 oder neuer aktualisieren; der Import
  prüft das und sagt es klar.

## 4. Design und Bedienung

- **Basisvorlage:** Eine Basisvorlage für alle Seiten im neuen Design aus Elo
  v1.0.41: Farbverlauf-Hero, Initialen-Avatare, Chips, Kacheln, Karten-Listen
  auf dem Handy, Toasts, Lade-Buttons. Technik: Bootstrap 5.3; die
  Tabler-Elemente aus Elo werden nachgebildet, Penalty bleibt bei Bootstrap
  5.3.
- **Menü:** Übersicht · Rangliste · Strafen · Verwaltung · Profil. Es zeigt
  nur aktive Module.
- **Strafen-Seiten:** werden auf dieselben Komponenten umgestellt.
- **Hell/Dunkel und Sprache:** pro Konto, wie heute in Penalty.

## 5. Ausbauplan

| Phase | Inhalt | Ergebnis |
|---|---|---|
| **0** | Grundgerüst: Abzweig, Name/Branding „Vereinsportal“, Modul-Schalter `MODULES`, Menü-Register, Tests grün | Portal = heutiges Penalty, Module schaltbar |
| **1** | Design: neue Basisvorlage + UI-Kit, Strafen-Seiten umgestellt, Screenshots | Zieldesign steht |
| **2** | Elo-Kern: Modelle, Elo-Rechnung, Neuberechnung, Rangliste, Statistik, Head-to-Head + portierte Tests | Rechenlogik identisch zu Elo |
| **3** | Elo-Oberfläche + API: Dashboard, Match eintragen, Statistik, Head-to-Head, Verwaltung, PDF/CSV, QR-Login, Deutsch/Englisch | Elo-Modul bedienbar |
| **4** | Import: `import_elo` + `import_strafen` mit Vorschau, Zuordnung, Transaktion, Prüfbericht; Admin-Upload | Datenübernahme beider Systeme |
| **5** | „Meine Übersicht“ (Elo + Strafen), Vereinskonten, Rollen-Feinschliff | Portal-Startseite |
| **6** | Ein Image, Compose/Portainer-Beispiel, Umstiegsanleitung, End-to-End-Test mit echten Kopien beider Datenbanken | Bereit zum Umstieg |

Jede Phase endet mit Tests und Screenshots zur Freigabe.

## 6. Umstieg (Kurzfassung)

1. Backups beider alten Systeme ziehen (Elo: „System → Download Backup“,
   Strafen: Volume-Kopie).
2. Portal-Container auf das **Strafen-Volume** starten. Die Datenbank wird
   übernommen und migriert.
3. Im Portal Elo einschalten und die **Elo-Datenbank importieren**: Vorschau,
   Zuordnung, Import, Prüfbericht.
4. Kontrollieren, dann die alten Container stoppen.

## 7. Was aus den bisherigen Arbeiten wird

- Elo `feat/ui-redesign`: Das Design wird zur Vorlage des Portals.
  Unabhängig davon kann es weiter als Elo v1.0.41 veröffentlicht werden.
- Elo `feat/portal-integration` (SSO-Add-in für drei Container): wird bei
  diesem Plan **nicht** gebraucht und bleibt unveröffentlicht.
- Alle Elo-Fehlerbehebungen und Regeln (Rangliste, Validierung, Sicherheit)
  sind Grundlage der Portierung.
