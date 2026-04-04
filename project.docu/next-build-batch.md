# ARIA - Next Build Batch

Stand: 2026-04-03

Zweck:
- Sammelliste fuer Punkte, die bewusst **erst mit einem spaeteren sinnvollen Image-Build** in den Container gehen sollen
- erledigte Punkte wandern in `project.docu/alpha-build-log.md`
- wir bauen nicht mehr fuer jeden kleinen Einzel-Fix ein neues Image

## Regel

- kleine UI-/Text-/Layout-Fixes zuerst sammeln
- erst bei einem inhaltlich sinnvollen Paket neu bauen
- dann:
  - neues TAR erzeugen
  - `aria-pull` auf `ubnsrv-aiagent` ausfuehren

## Noch offen fuer spaetere Builds

### 1. Version verfuegbar statt In-App-Update

Produktidee:
- kein `Update jetzt`-Button fuer Docker/Portainer in der UI
- stattdessen ein Hinweis, wenn eine neuere Version auf Docker Hub/GitHub Releases verfuegbar ist

Ziel:
- hilfreiche Update-Transparenz fuer User
- ohne gefaehrlichen Schein einer vollautomatischen Container-Selbstaktualisierung

### 2. Memory-Export / spaeter Import

Produktidee:
- persoenliche Memories exportierbar machen
- Zielbild: Erinnerungen sichern, mitnehmen und spaeter wieder importieren

Naechste Aenderung:
- Exportformat fuer persoenliche Memories definieren
- spaeter optional Import dazu

Ziel:
- staerkeres Single-User-/Personal-Assistant-Gefuehl
- User behalten die Kontrolle ueber ihre persoenlichen Erinnerungen

### 3. Stats: `Aktivitaeten & Runs` noch kompakter in eine gemeinsame KPI-Box ziehen

Aktueller Befund:
- die vier Activity-Kennzahlen stehen bereits auf einer Linie/sauberem Grid
- gewuenscht ist aber perspektivisch eher **eine gemeinsame kompakte Box** ueber die ganze Breite

Naechste Aenderung:
- `Aktivitaeten`, `Erfolgreich`, `Mit Fehlern`, `Ø Dauer` in eine gemeinsame Box ziehen
- iPhone-/Mobile-Fallback sauber beibehalten

Ziel:
- noch ruhigerer Stats-Block
- weniger visuelles Springen

## Kontext

Diese Liste ist bewusst **kein allgemeiner Backlog**.
Sie ist nur fuer Punkte gedacht, die:
- sinnvoll sind
- aber **keinen Sofort-Build rechtfertigen**
