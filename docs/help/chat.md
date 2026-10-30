# Chat, Queue und Bestätigungen

Stand: 2026-10-25

## Zweck

Der Chat ist ARIAs Arbeitsfläche für Fragen, lokale Kontextsuche und kontrollierte Aktionen. ARIA soll nicht nur Text beantworten, sondern ein Ziel verstehen, Kontext laden, bei Bedarf eine Aktion planen, Guardrails anwenden, ausführen und das Ergebnis nachvollziehbar machen.

## Prompt Queue

Wenn ARIA gerade arbeitet, bleibt das Eingabefeld aktiv. Neue Prompts werden in die Warteschlange gelegt und danach sequentiell ausgeführt.

Du kannst wartende Prompts:

- umsortieren
- bearbeiten
- entfernen

Die Warteschlange bleibt bei einem Reload erhalten. Läuft dabei gerade eine Antwort, wird sie im Chat als Hintergrund-Auftrag weitergeführt; sobald dieser fertig ist, setzt ARIA die Warteschlange automatisch fort. In Vibe:Lab läuft der aktive Lauf ebenfalls weiter und die erhaltene Warteschlange startet danach automatisch.

## Chats verwalten

Der Titel im Kopf öffnet den Chat-Umschalter. Dort kannst du einen leeren neuen Chat beginnen, frühere Chats durchsuchen und wieder öffnen sowie Chats umbenennen, anheften, archivieren oder nach Bestätigung löschen. **Alle Chats** zeigt aktive und archivierte Unterhaltungen in einer eigenen Übersicht.

Ein neuer Chat beginnt immer ohne den Kontext anderer Chats. Der bisherige Verlauf wird beim Update verlustfrei als **Bisheriger Verlauf** übernommen; die ursprüngliche JSON-Datei bleibt als Sicherung erhalten. Archivierte Chats werden standardmässig nach 90 Tagen gelöscht. Administratoren können die Frist unter **Einstellungen → Betrieb** ändern.

Über das Menü **⋯** an einem eigenen Prompt kannst du genau diese Runde, alle Runden ab dort oder den Prompt zum Bearbeiten und erneuten Senden wählen. Eine Löschung bleibt zehn Sekunden rückgängig machbar. Beim anschliessenden Commit entfernt ARIA nur Memory-Einträge, deren gespeicherte Herkunft exakt auf die gelöschten Turn-IDs verweist; Textähnlichkeit ist niemals Löschgrundlage.

## Laufende Anfrage abbrechen

Der Abbrechen-Button stoppt die aktuelle Browser-Anfrage. Bereits an externe Systeme gesendete read-only Requests können serverseitig trotzdem fertiglaufen; ARIA startet aber keinen zweiten Queue-Eintrag parallel.

## Pending Confirmations

Aktionen mit Side-Effect oder erhöhtem Risiko können eine Bestätigung brauchen. ARIA zeigt diese bestätigungspflichtigen Aktionen als sichtbaren Queue-Eintrag mit eigenem Status.

Mögliche Aktionen:

- **Ausführen** führt die vorbereitete Aktion aus, solange die Bestätigung noch gültig ist.
- **Neu planen** stellt den ursprünglichen Prompt erneut in die Queue oder startet ihn neu.
- **Verwerfen** entfernt die wartende Bestätigung.

Abgelaufene oder ungültige Bestätigungen werden nicht automatisch ausgeführt. Plane die Aktion neu, wenn du sie weiterhin willst.

## Details lesen

Unter **Details** zeigt ARIA je nach Antwort:

- geladene Quellen aus Memory, Dokumenten oder Websuche
- Routing- und Operator-Trace-Linien
- geplante Capability, Connection und Runtime-Grenze
- Policy-/Guardrail-Entscheidungen
- Token, Kosten und Laufzeit

Diese Details sind besonders nützlich, wenn ARIA ein Ziel falsch verstanden hat oder eine Aktion blockiert.

## Chat exportieren

Mit **Chat exportieren** erstellt ARIA einen Markdown-Export des aktuell sichtbaren Chats. Der Export enthält User-Prompts, ARIA-Antworten, Token-/Kosten-/Laufzeit-Badges und alle Routing-/Debug-/Operator-Trace-Zeilen aus den Details, auch wenn diese im Browser eingeklappt sind.

ARIA kopiert den Export zuerst in die Zwischenablage. Wenn der Browser das blockiert, wird automatisch eine `.md`-Datei heruntergeladen.

## Mobile und iOS

Der Chat nutzt eine feste mobile Arbeitsfläche mit eigener Scroll-Historie. Auf iPhone/iPad bleiben Composer, Queue und Toolbox erreichbar. Lange Prompts und Bestätigungsbuttons dürfen umbrechen, damit sie auf schmalen Viewports nicht abgeschnitten werden.

## Gute Tests nach einem Update

- während einer langen Antwort einen zweiten Prompt eingeben
- zwei wartende Prompts umsortieren
- einen wartenden Prompt bearbeiten und einen entfernen
- eine bestätigungspflichtige Aktion planen, aber nicht sofort ausführen
- den Chat exportieren und prüfen, ob Details/Debug-Zeilen enthalten sind
- dieselbe Ansicht auf iPhone-Breite prüfen
