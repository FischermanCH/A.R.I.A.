# Vibe:Lab

Vibe:Lab ist der Arbeitsraum für Entwicklung direkt in ARIA. Ein Projekt kann Fenster für einen Coding-Agenten, einen fokussierten LLM-Chat und ein direktes Terminal enthalten. Über **Layout** ordnest du ein bis vier Fenster an. Modell und Denkaufwand wählst du pro Fenster.

## Warum der Agent in einer Arbeitskopie arbeitet

Jeder Agent-Lauf arbeitet in einem eigenen Git-Worktree, also in einer isolierten Kopie. Dadurch bleiben dein Projektordner und parallele Arbeiten sicher, und nichts Halb-Fertiges landet unbemerkt im Projekt. Änderungen werden erst mit **Ins Projekt übernehmen** sichtbar. Das schreibt sie lokal in dein Projekt und führt keinen Push aus. Prüfe vorher **Änderungen**. Mit **Verwerfen** setzt du die Arbeitskopie zurück.

Eine Fortsetzung baut auf derselben Arbeitskopie und demselben Kontext auf; die Zeile **Setzt fort** zeigt das an. **Neuer Lauf** beginnt mit frischem Kontext.

## Fenster und Autonomie

- **Agent** bearbeitet Dateien und führt Werkzeuge aus. L0 verlangt Freigaben für jede schreibende oder ausführende Aktion. L1 erlaubt eng begrenzte Projektarbeit, L2 arbeitet weitergehend selbstständig, L3 ist die weiteste verfügbare Autonomie. ARIAs feste Sicherheitsgrenzen gelten immer.
- **LLM-Chat** ist ein fokussiertes Gespräch zum Projekt, ohne selbstständige Dateiänderungen.
- **Terminal** führt deine Eingaben direkt aus; diese Befehle sind keine Agent-Aktionen.

Wenn eine Aktion nicht vom aktuellen Autonomie-Level gedeckt ist, erscheint unten eine angeheftete Freigabekarte und oben das Freigabeband. Erlauben oder Ablehnen wirkt auf genau diese Anfrage. Benachrichtigungen können zusätzlich über Discord gemeldet werden.

## Dateien, Bilder und Befehle

Über **Datei hochladen (Bild, Dokument)** öffnest du die Austauschdateien. Bilder kannst du auch einfügen; die Vorschau erscheint vor dem Senden und bleibt danach in der Nachricht verfügbar. `/cls` und `/clear` archivieren beziehungsweise leeren das aktuelle Fenster entsprechend seinem Typ.

Vibe:Lab synchronisiert laufende Zustände und neue Antworten zwischen geöffneten Geräten. Ist der Coding-Host nicht erreichbar, bleibt der Verlauf erhalten: prüfe die Verbindung, nutze **Erneut versuchen** und starte erst danach einen neuen Lauf. Bereits sichtbare Änderungen kannst du weiterhin prüfen oder verwerfen.

Wenn ein Lauf hängt → **Technische Details** → **Kopieren**. Füge die kopierten Angaben einer Fehlermeldung bei; sie enthalten den Laufzustand, aber keine geheimen Zugangsdaten.
