# Navigation, Menüs und Erweiterte Ansicht

Stand: 2026-07-09

## Zweck

ARIAs Navigation ist in Bereiche aufgeteilt, damit Alltagsarbeit und technische Pflege nicht im selben Menü miteinander konkurrieren. Der Header, das Account-Menü und die Bereichsnavigation folgen derselben Struktur.

## Header

Der Header zeigt die aktuelle Hauptnavigation für den Bereich, in dem du gerade arbeitest. Unterseiten sollen nicht plötzlich in ein anderes Hauptmenü springen:

- Settings-Unterseiten behalten die Settings-Navigation.
- Admin-Unterseiten behalten die Admin-Navigation.
- Memory-Unterseiten behalten die Memory-Navigation.
- Recipes und Connections behalten ihren eigenen Bereichskontext.

Detailfunktionen liegen als Karten oder Inhalte auf der Seite, nicht als wechselnde Header-Sondermenüs.

## Account-Menü

Das Account-Menü ist der Einstieg in die großen Bereiche:

- Chat
- Memory
- Notizen
- Einstellungen
- Statistiken
- Updates, wenn relevant
- Hilfe

Wenn **Erweiterte Ansicht** aktiv ist, wird **Einstellungen** im Account-Menü zu einem aufklappbaren Eintrag mit **Einstellungen** und **Admin**. Damit bleibt Admin erreichbar, ohne die normale Alltagsnavigation zu überladen.

## Erweiterte Ansicht

**Erweiterte Ansicht** ersetzt die frühere Admin-Modus-Sprache in der normalen UI. Sie schaltet technische Bereiche sichtbar, ändert aber nicht automatisch deine Rolle.

Wichtig:

- Nur berechtigte Admins können Admin-Funktionen nutzen.
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

`/config/admin` ist die Admin-Übersicht. Admin ist in echte Gruppen aufgeteilt:

- **Systemkonfiguration**
- **Rezepte**
- **Memory**
- **Betrieb**

Jede Gruppe hat eine eigene Seite. Ein Klick auf eine Admin-Gruppe wechselt sichtbar den Inhalt, statt nur auf einen Anker innerhalb einer langen Seite zu springen.

## Memory

Memory ist ein eigener Bereich:

- `/memories` zeigt den grafischen Gedächtnis-Browser.
- `/memories/import` importiert Dokumente und Memory-Daten.
- `/memories/create` erfasst manuelle Erinnerungen.
- `/memories/auto-memory` zeigt das persönliche Modell.
- `/memories/maintenance` sammelt technische Pflege.

Memory-Wartung ist nicht mehr als globale Admin-Abkürzung verdoppelt, sondern bleibt im Memory-Kontext.

## Rezepte

Recipes sind als eigener Bereich gegliedert:

- `/recipes` ist der Rezepte-Hub.
- `/recipes/mine` ist die Arbeitsliste für gespeicherte Rezepte.
- `/recipes/start` und `/recipes/templates` helfen beim Erstellen und Importieren.
- `/recipes/system` zeigt mitgelieferte Systemrezepte.

## Connections

Connections sind über Settings erreichbar, behalten aber einen eigenen Bereichskontext. Die Übersicht ist absichtlich kein Live-Status-Dashboard; operative Signale gehören in Stats oder dedizierte Statusseiten.

## Mobile und iOS

Auf schmalen Viewports dürfen Menüs, Tabs und Hilfelinks umbrechen. Der Account-Einstieg bleibt der zentrale Weg, wenn Header-Navigation nicht alles gleichzeitig zeigen kann.

## Gute Tests nach einem Update

- Account-Menü mit und ohne Erweiterte Ansicht öffnen
- `/config`, `/config/access` und `/config/operations` prüfen
- `/memories`, `/memories/import`, `/memories/auto-memory` und `/memories/maintenance` prüfen
- `/recipes`, `/recipes/mine`, `/recipes/start` und `/recipes/system` prüfen
- dieselben Wege auf iPhone-Breite prüfen
