# Navigation, Menues und Erweiterte Ansicht

Stand: 2026-07-09

## Zweck

ARIAs Navigation ist in Bereiche aufgeteilt, damit Alltagsarbeit und technische Pflege nicht im selben Menue miteinander konkurrieren. Der Header, das Account-Menue und die Bereichsnavigation folgen derselben Struktur.

## Header

Der Header zeigt die aktuelle Hauptnavigation fuer den Bereich, in dem du gerade arbeitest. Unterseiten sollen nicht ploetzlich in ein anderes Hauptmenue springen:

- Settings-Unterseiten behalten die Settings-Navigation.
- Admin-Unterseiten behalten die Admin-Navigation.
- Memory-Unterseiten behalten die Memory-Navigation.
- Recipes und Connections behalten ihren eigenen Bereichskontext.

Detailfunktionen liegen als Karten oder Inhalte auf der Seite, nicht als wechselnde Header-Sondermenues.

## Account-Menue

Das Account-Menue ist der Einstieg in die grossen Bereiche:

- Chat
- Memory
- Notizen
- Einstellungen
- Statistiken
- Updates, wenn relevant
- Hilfe

Wenn **Erweiterte Ansicht** aktiv ist, wird **Einstellungen** im Account-Menue zu einem aufklappbaren Eintrag mit **Einstellungen** und **Admin**. Damit bleibt Admin erreichbar, ohne die normale Alltagsnavigation zu ueberladen.

## Erweiterte Ansicht

**Erweiterte Ansicht** ersetzt die fruehere Admin-Modus-Sprache in der normalen UI. Sie schaltet technische Bereiche sichtbar, aendert aber nicht automatisch deine Rolle.

Wichtig:

- Nur berechtigte Admins koennen Admin-Funktionen nutzen.
- Wenn Erweiterte Ansicht aus ist, bleiben normale Arbeitsbereiche sichtbar.
- Technische Systemseiten werden ausgeblendet, damit die normale Bedienung ruhiger bleibt.
- Du kannst die Option unter `/config/admin-mode` umschalten.

## Einstellungen

`/config` ist der ruhige Settings-Hub. Dort findest du Alltags- und Betriebsoptionen wie:

- LLM und Embeddings
- Aussehen und Sprache
- Verbindungen und Rezepte
- Updates
- Logs und Backup
- Zugriff und Security

Viele technische Details erscheinen erst bei aktiver Erweiterter Ansicht.

## Admin

`/config/admin` ist die Admin-Uebersicht. Admin ist in echte Gruppen aufgeteilt:

- **Systemkonfiguration**
- **Rezepte & Lernen**
- **Memory**
- **Betrieb**

Jede Gruppe hat eine eigene Seite. Ein Klick auf eine Admin-Gruppe wechselt sichtbar den Inhalt, statt nur auf einen Anker innerhalb einer langen Seite zu springen.

## Memory

Memory ist ein eigener Bereich:

- `/memories` zeigt den grafischen Gedaechtnis-Browser.
- `/memories/import` importiert Dokumente und Memory-Daten.
- `/memories/create` erfasst manuelle Erinnerungen.
- `/memories/auto-memory` erklaert Auto-Memory und Lernen.
- `/memories/maintenance` sammelt technische Pflege.

Memory-Wartung ist nicht mehr als globale Admin-Abkuerzung verdoppelt, sondern bleibt im Memory-Kontext.

## Rezepte

Recipes sind als eigener Bereich gegliedert:

- `/recipes` ist der Rezepte-Hub.
- `/recipes/mine` ist die Arbeitsliste fuer gespeicherte Rezepte.
- `/recipes/start` und `/recipes/templates` helfen beim Erstellen und Importieren.
- `/recipes/learned` ist die normale Learned-Recipes-Ansicht.
- `/recipes/learned/maintenance` ist die Admin-Pflege fuer gelernte Rezepte.

Systemrezepte und Pflegefunktionen bleiben bewusst im Admin-Kontext.

## Connections

Connections sind ueber Settings erreichbar, behalten aber einen eigenen Bereichskontext. Die Uebersicht ist absichtlich kein Live-Status-Dashboard; operative Signale gehoeren in Stats oder dedizierte Statusseiten.

## Mobile und iOS

Auf schmalen Viewports duerfen Menues, Tabs und Hilfelinks umbrechen. Der Account-Einstieg bleibt der zentrale Weg, wenn Header-Navigation nicht alles gleichzeitig zeigen kann.

## Gute Tests nach einem Update

- Account-Menue mit und ohne Erweiterte Ansicht oeffnen
- `/config`, `/config/admin`, `/config/admin/memory` und `/config/admin/operations` pruefen
- `/memories`, `/memories/import`, `/memories/auto-memory` und `/memories/maintenance` pruefen
- `/recipes`, `/recipes/mine`, `/recipes/learned` und `/recipes/learned/maintenance` pruefen
- dieselben Wege auf iPhone-Breite pruefen
