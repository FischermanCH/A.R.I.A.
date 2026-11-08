# Vibe:Lab

Vibe:Lab ist ARIAs Entwicklungsumgebung für mehrere Projekte und Werkzeuge in einer gemeinsamen Ansicht.

## Workspaces und Projekte

Ein **Workspace** ist eine gespeicherte Anordnung von bis zu vier Fenstern. Er merkt sich, welche Projekte an welche Fenster gebunden sind, ob die Fenster nebeneinander oder übereinander liegen und wie gross die einzelnen Bereiche sind. Ein Workspace hat keinen eigenen Ordner. Du kannst ihn in der oberen Leiste erstellen, umbenennen oder löschen; Änderungen am Layout werden automatisch gespeichert.

Ein **Projekt** enthält den Projektordner, die Zuordnung zum Coding-Agent und dessen Host, das Autonomie-Level sowie die Vorgaben für LLM und Modell. Hier liegen die Arbeitsdaten wie Uploads, Agent-Läufe und Verlauf. Projekte verwaltest du über den Reiter **Vibe:Lab-Projekte** unter `/vibelab/projects`. Die Coding-Agent- und SSH-Verbindungen selbst richtest du im Bereich **Verbindungen** beziehungsweise in der Konfiguration ein.

Mehrere Projekte können gleichzeitig im selben Workspace laufen. Du kannst beispielsweise mehrere Coding-Agent-Fenster öffnen und jedes an ein anderes Projekt binden.

## Fenstertypen

- **LLM-Chat** steht allen Benutzerinnen und Benutzern für ein fokussiertes Gespräch zum gebundenen Projekt zur Verfügung.
- **Coding-Agent** ist für Administratorinnen und Administratoren verfügbar. Er bearbeitet Dateien und führt Werkzeuge im gebundenen Projekt aus.
- **Terminal** ist für Administratorinnen und Administratoren verfügbar. Es öffnet eine direkte SSH-Shell zum Coding-Host des gebundenen Projekts; ein eigenständiges Fenster für eine beliebige SSH-Verbindung gibt es nicht.

## Warum der Agent in einer Arbeitskopie arbeitet

Jeder Agent-Lauf arbeitet in einem eigenen Git-Worktree, also in einer isolierten Kopie. Dadurch bleiben dein Projektordner und parallele Arbeiten sicher, und nichts Halb-Fertiges landet unbemerkt im Projekt. Änderungen werden erst mit **Ins Projekt übernehmen** sichtbar. Das schreibt sie lokal in dein Projekt und führt keinen Push aus. Prüfe vorher **Änderungen**. Mit **Verwerfen** setzt du die Arbeitskopie zurück.

Eine Fortsetzung baut auf derselben Arbeitskopie und demselben Kontext auf; die Zeile **Setzt fort** zeigt das an. **Neuer Lauf** beginnt mit frischem Kontext.

## Autonomie und Freigaben

L0 verlangt Freigaben für jede schreibende oder ausführende Agent-Aktion. L1 erlaubt eng begrenzte Projektarbeit, L2 arbeitet weitergehend selbstständig, L3 ist die weiteste verfügbare Autonomie. ARIAs feste Sicherheitsgrenzen gelten immer. Befehle im Terminal gibst du direkt ein; sie sind keine Agent-Aktionen.

Wenn eine Aktion nicht vom aktuellen Autonomie-Level gedeckt ist, erscheint unten eine angeheftete Freigabekarte und oben das Freigabeband. Erlauben oder Ablehnen wirkt auf genau diese Anfrage. Benachrichtigungen können zusätzlich über Discord gemeldet werden.

## Dateien, Bilder und Befehle

Über **Datei hochladen (Bild, Dokument)** öffnest du die Austauschdateien. Bilder kannst du auch einfügen; die Vorschau erscheint vor dem Senden und bleibt danach in der Nachricht verfügbar. `/cls` und `/clear` archivieren beziehungsweise leeren das aktuelle Fenster entsprechend seinem Typ.

Vibe:Lab synchronisiert laufende Zustände und neue Antworten zwischen geöffneten Geräten. Ist der Coding-Host nicht erreichbar, bleibt der Verlauf erhalten: prüfe die Verbindung, nutze **Erneut versuchen** und starte erst danach einen neuen Lauf. Bereits sichtbare Änderungen kannst du weiterhin prüfen oder verwerfen.

Wenn ein Lauf hängt → **Technische Details** → **Kopieren**. Füge die kopierten Angaben einer Fehlermeldung bei; sie enthalten den Laufzustand, aber keine geheimen Zugangsdaten.
