# Vibe:Lab

Vibe:Lab verbindet Coding-Agents, Terminal und ARIAs Hauptchat in einer gemeinsamen Arbeitsansicht.

## Verbindungen, Agents und Workspaces

Eine **Verbindung** stellt den SSH-Zugang und die erlaubten Ordner bereit. Ein **Agent** verbindet einen solchen Zugang mit einem Arbeitsordner, dem Agent-Typ sowie den Standardwerten für Autonomie, Modell und Budget. Zwei Agents dürfen denselben Ordner verwenden, etwa einmal mit Codex und einmal mit Claude.

Ein **Workspace** speichert nur die Anordnung von bis zu vier Fenstern. Er besitzt keinen Arbeitsordner. Du kannst ihn oben erstellen, umbenennen oder löschen; das Layout wird automatisch gespeichert. Das Löschen eines Workspace löscht keine Agents und keine Agent-Arbeitsdaten. Verbindungen und Agents verwaltest du unter `/vibelab/projects`.

## Fenstertypen

- **LLM** zeigt standardmässig denselben aktiven Chat wie ARIAs Hauptchat, einschliesslich dessen Verlauf und Memory. Eine bestimmte Unterhaltung kann später ausdrücklich gebunden werden.
- **Agent** arbeitet mit dem gewählten Agent im zugehörigen Ordner und ist für Administratorinnen und Administratoren verfügbar.
- **Terminal** öffnet für Administratorinnen und Administratoren eine direkte Shell über die gewählte Verbindung.

## Sichere Arbeitskopien und Freigaben

Jeder Agent-Lauf arbeitet in einem eigenen Git-Worktree. Änderungen gelangen erst mit **In Arbeitsordner übernehmen** in den lokalen Arbeitsordner; dabei erfolgt kein Push. Prüfe vorher **Änderungen**. **Neuer Lauf** beginnt mit frischem Kontext, während die Standardeingabe den letzten Lauf fortsetzt.

L0 verlangt Freigaben für schreibende oder ausführende Aktionen. L1 erlaubt eng begrenzte Arbeit, L2 arbeitet weitergehend selbstständig und L3 ist die weiteste verfügbare Autonomie. ARIAs Sicherheitsregeln gelten immer. Wenn eine Aktion nicht gedeckt ist, erscheint **Freigabe nötig** direkt bei der Eingabe. **Setzt fort** kennzeichnet die Fortsetzung eines bestehenden Laufs; `/cls` und `/clear` archivieren beziehungsweise leeren das aktuelle Fenster.

Uploads und Läufe bleiben beim Agent gespeichert. Vibe:Lab synchronisiert laufende Zustände zwischen geöffneten Geräten. Ist ein Host nicht erreichbar, bleibt der Verlauf erhalten; prüfe die Verbindung und nutze **Erneut versuchen**.

Wenn ein Lauf hängt → **Technische Details** → **Kopieren**. Die Angaben enthalten den Laufzustand, aber keine geheimen Zugangsdaten.
