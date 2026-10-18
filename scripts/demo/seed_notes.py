#!/usr/bin/env python3
"""Write fictitious, public-safe demo notes into the generated demo seed."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil

import yaml


DEMO_USER = "demo-admin"
ANCHOR = datetime(2026, 10, 10, 14, 30, tzinfo=timezone.utc)

# (slug, folder, title, tags, days_before_anchor, body)
NOTES: tuple[tuple[str, str, str, list[str], float, str], ...] = (
    ("backup-strategie", "Homelab", "Backup-Strategie 3-2-1", ["homelab", "backup"], 0.2, """\
Ziel: jede wichtige Datei liegt **dreimal** vor, auf **zwei** Medien, **eine** Kopie ausser Haus.

| Daten | Ziel | Rhythmus | Aufbewahrung |
|---|---|---|---|
| Fotos | Demo Archive (SFTP) | täglich 02:00 | 90 Tage |
| Dokumente | Demo Library (SMB) | stündlich | 30 Tage |
| Konfigurationen | Git-Repo | bei Änderung | unbegrenzt |
| VM-Snapshots | externe Disk | wöchentlich | 4 Wochen |

## Offene Punkte

- [x] Restore-Test für Fotos durchgeführt
- [x] Benachrichtigung bei Fehlern an Demo Community
- [ ] Offsite-Kopie verschlüsseln
- [ ] Restore-Test für VM-Snapshots planen
"""),
    ("docker-compose-monitoring", "Homelab", "Monitoring-Stack mit Docker Compose", ["homelab", "docker", "monitoring"], 1.5, """\
Kleiner Monitoring-Stack für die Demo-Werkstatt. Läuft auf `workshop.example.org`.

```yaml
services:
  uptime:
    image: louislam/uptime-kuma:1
    restart: unless-stopped
    ports:
      - "3001:3001"
    volumes:
      - uptime-data:/app/data

  node-exporter:
    image: prom/node-exporter:latest
    restart: unless-stopped
    pid: host

volumes:
  uptime-data:
```

Nach dem Start: Checks für *Demo Handbook* und *Demo Catalog API* anlegen, Intervall 60 s.
"""),
    ("raspberry-pi-sensoren", "Homelab", "Raspberry Pi Sensoren", ["homelab", "mqtt"], 4, """\
Drei Sensoren melden an `mqtt.example.org`, Topic `demo/status`.

- Wohnzimmer: Temperatur + Luftfeuchte
- Keller: Feuchtigkeit (Warnung ab 65 %)
- Balkon: Temperatur, Sonnenschutz nötig

Nächster Schritt: Werte im Dashboard als Wochenverlauf zeigen.
"""),
    ("update-checkliste", "Homelab", "Update-Checkliste Server", ["homelab", "wartung"], 6, """\
Vor jedem Update-Abend:

1. Backups prüfen (letzter Lauf grün?)
2. Changelog der wichtigsten Pakete lesen
3. Snapshot der VMs erstellen
4. Updates auf *Demo Workshop* zuerst, dann *Demo Observatory*
5. Dienste und Healthchecks kontrollieren

- [x] Oktober erledigt
- [ ] November eintragen
"""),
    ("zopf", "Rezepte", "Sonntagszopf", ["rezept", "backen"], 2, """\
Für einen Zopf von ca. 1 kg.

| Zutat | Menge |
|---|---|
| Zopfmehl | 500 g |
| Milch | 3 dl |
| Butter, weich | 60 g |
| Hefe | 20 g |
| Salz | 1½ TL |
| Zucker | 1 TL |
| Ei zum Bestreichen | 1 |

## Zubereitung

1. Alles ausser dem Ei 10 Minuten kneten.
2. Zugedeckt 1½ Stunden aufgehen lassen.
3. Zwei Stränge formen und flechten.
4. Mit Ei bestreichen, 30 Minuten kühl stellen.
5. Bei 200 °C ca. 35 Minuten backen.

> Tipp: Am Vorabend kneten und über Nacht im Kühlschrank gehen lassen.
"""),
    ("linsen-curry", "Rezepte", "Rotes Linsen-Curry", ["rezept", "vegetarisch"], 8, """\
Schnell, günstig, für 4 Personen.

- 250 g rote Linsen
- 1 Dose Kokosmilch
- 1 Dose gehackte Tomaten
- 1 Zwiebel, 2 Knoblauchzehen, Ingwer
- 2 EL Currypaste, Salz, Limette

Zwiebel, Knoblauch und Ingwer andünsten, Currypaste kurz mitrösten. Linsen, Tomaten und Kokosmilch dazu, 20 Minuten köcheln. Mit Limette abschmecken, mit Reis servieren.
"""),
    ("einkaufsliste-wochenende", "Rezepte", "Einkaufsliste Wochenende", ["einkauf"], 0.6, """\
- [x] Zopfmehl
- [x] Butter
- [ ] Hefe
- [ ] Rote Linsen
- [ ] Kokosmilch
- [ ] Limetten
- [ ] Kaffee
"""),
    ("aria-sprachsteuerung", "Projektideen", "Sprachsteuerung für die Werkstatt", ["idee", "aria"], 3, """\
Idee: In der Werkstatt per Sprache fragen, ob alle Dienste laufen.

**Ablauf**

1. Wake-Word lokal erkennen
2. Frage an ARIA schicken
3. Antwort kurz vorlesen, Details im Chat ablegen

**Fragen**

- Reicht ein Mikrofon-Array für einen lauten Raum?
- Welche Aktionen brauchen trotzdem eine Bestätigung am Bildschirm?
"""),
    ("garten-bewaesserung", "Projektideen", "Automatische Gartenbewässerung", ["idee", "garten", "mqtt"], 12, """\
Bodenfeuchte-Sensor pro Beet, Ventil per MQTT schalten.

- Gießen nur, wenn Feuchte < 30 % **und** kein Regen angesagt
- Maximal 10 Minuten pro Durchgang
- Wochenbericht als Notiz ablegen

Budget: ca. 120 CHF für Sensoren und Ventile.
"""),
    ("lesestapel", "Projektideen", "Lesestapel Herbst", ["lesen"], 15, """\
- [x] *Designing Data-Intensive Applications*
- [ ] *The Pragmatic Programmer*
- [ ] *Thinking in Systems*
- [ ] Artikelserie zu lokalen Sprachmodellen aus dem Demo-Feed
"""),
    ("tessin-wochenende", "Reise", "Wochenende im Tessin", ["reise", "wandern"], 5, """\
**Freitag** – Anreise mit dem Zug, Abendessen am See
**Samstag** – Wanderung, ca. 4 h, Picknick mitnehmen
**Sonntag** – Markt am Vormittag, Rückfahrt am Nachmittag

## Packliste

- [x] Wanderschuhe
- [x] Regenjacke
- [ ] Sonnencreme
- [ ] Ladegerät und Powerbank
- [ ] Halbtax / Tickets
"""),
    ("sprint-review", "Meetings", "Sprint-Review Demo-Team", ["meeting", "team"], 1, """\
**Teilnehmende:** Alex, Sam, Robin

## Ergebnisse

- Neue Übersicht für Hintergrund-Jobs ist fertig
- RSS-Kategorien funktionieren, 32 Demo-Feeds sortiert
- Offline-Modus für die Demo-Instanz getestet

## Entscheidungen

- Bestätigungen bleiben für jede schreibende Aktion Pflicht
- Screenshots kommen nur aus der Demo-Instanz

## Aufgaben

- [ ] Alex: Hilfetexte für Notizen ergänzen
- [ ] Sam: Ladezeiten der Startseite messen
- [x] Robin: Demo-Daten aktualisieren
"""),
    ("retro-oktober", "Meetings", "Retro Oktober", ["meeting", "retro"], 9, """\
| Gut gelaufen | Verbessern | Ausprobieren |
|---|---|---|
| Kurze Builds | Zu viele offene Tickets | Fokus-Tage ohne Meetings |
| Klare Testprompts | Doku hinkt hinterher | Pair-Review am Freitag |

Nächste Retro in vier Wochen.
"""),
)


def _build_markdown(meta: dict[str, object], body: str) -> str:
    frontmatter = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{frontmatter}\n---\n\n{body.strip()}\n"


def seed_notes(data: Path) -> int:
    """Recreate the demo user's notes deterministically; return the note count."""

    root = data / "notes" / DEMO_USER
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    for index, (slug, folder, title, tags, days, body) in enumerate(NOTES, start=1):
        updated = ANCHOR - timedelta(days=days)
        created = updated - timedelta(days=2, hours=index)
        meta = {
            "note_id": f"demo-note-{index:02d}",
            "title": title,
            "folder": folder,
            "created_at": created.isoformat(),
            "updated_at": updated.isoformat(),
            "tags": tags,
        }
        target = root / folder / f"{slug}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_build_markdown(meta, body), encoding="utf-8")
    return len(NOTES)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    count = seed_notes(args.root / "demo" / "generated" / "data")
    print(f"Demo notes seeded: {count}")


if __name__ == "__main__":
    main()
