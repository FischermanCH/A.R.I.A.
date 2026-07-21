# Chat, Queue und Bestaetigungen

Stand: 2026-07-09

## Zweck

Der Chat ist ARIAs Arbeitsflaeche fuer Fragen, lokale Kontextsuche und kontrollierte Aktionen. ARIA soll nicht nur Text beantworten, sondern ein Ziel verstehen, Kontext laden, bei Bedarf eine Aktion planen, Guardrails anwenden, ausfuehren und das Ergebnis nachvollziehbar machen.

## Prompt Queue

Wenn ARIA gerade arbeitet, bleibt das Eingabefeld aktiv. Neue Prompts werden in die Warteschlange gelegt und danach sequentiell ausgefuehrt.

Du kannst wartende Prompts:

- umsortieren
- bearbeiten
- entfernen

Die Queue ist pro Browser-Tab. Sie ist nicht als dauerhaftes Aufgabenboard gedacht und ueberlebt keinen Reload oder Browser-Neustart.

## Laufende Anfrage abbrechen

Der Abbrechen-Button stoppt die aktuelle Browser-Anfrage. Bereits an externe Systeme gesendete read-only Requests koennen serverseitig trotzdem fertiglaufen; ARIA startet aber keinen zweiten Queue-Eintrag parallel.

## Pending Confirmations

Aktionen mit Side-Effect oder erhoehtem Risiko koennen eine Bestaetigung brauchen. ARIA zeigt diese bestaetigungspflichtigen Aktionen als sichtbaren Queue-Eintrag mit eigenem Status.

Moegliche Aktionen:

- **Ausfuehren** fuehrt die vorbereitete Aktion aus, solange die Bestaetigung noch gueltig ist.
- **Neu planen** stellt den urspruenglichen Prompt erneut in die Queue oder startet ihn neu.
- **Verwerfen** entfernt die wartende Bestaetigung.

Abgelaufene oder ungueltige Bestaetigungen werden nicht automatisch ausgefuehrt. Plane die Aktion neu, wenn du sie weiterhin willst.

## Details lesen

Unter **Details** zeigt ARIA je nach Antwort:

- geladene Quellen aus Memory, Dokumenten oder Websuche
- Routing- und Operator-Trace-Linien
- geplante Capability, Connection und Runtime-Grenze
- Policy-/Guardrail-Entscheidungen
- Token, Kosten und Laufzeit

Diese Details sind besonders nuetzlich, wenn ARIA ein Ziel falsch verstanden hat oder eine Aktion blockiert.

## Chat exportieren

Mit **Chat exportieren** erstellt ARIA einen Markdown-Export des aktuell sichtbaren Chats. Der Export enthaelt User-Prompts, ARIA-Antworten, Token-/Kosten-/Laufzeit-Badges und alle Routing-/Debug-/Operator-Trace-Zeilen aus den Details, auch wenn diese im Browser eingeklappt sind.

ARIA kopiert den Export zuerst in die Zwischenablage. Wenn der Browser das blockiert, wird automatisch eine `.md`-Datei heruntergeladen.

## Mobile und iOS

Der Chat nutzt eine feste mobile Arbeitsflaeche mit eigener Scroll-Historie. Auf iPhone/iPad bleiben Composer, Queue und Toolbox erreichbar. Lange Prompts und Bestaetigungsbuttons duerfen umbrechen, damit sie auf schmalen Viewports nicht abgeschnitten werden.

## Gute Tests nach einem Update

- waehrend einer langen Antwort einen zweiten Prompt eingeben
- zwei wartende Prompts umsortieren
- einen wartenden Prompt bearbeiten und einen entfernen
- eine bestaetigungspflichtige Aktion planen, aber nicht sofort ausfuehren
- den Chat exportieren und pruefen, ob Details/Debug-Zeilen enthalten sind
- dieselbe Ansicht auf iPhone-Breite pruefen
