# SearXNG in ARIA

Stand: 2026-04-21

SearXNG ist in ARIA der bevorzugte Dienst fuer selbst gehostete Websuche.

ARIA nutzt SearXNG fuer:

- Websuche mit Quellen
- kontrollierte Recherche ueber einen eigenen Stack-Dienst
- Weitergabe von Treffern in Chat-Antworten oder Kontexte

## Wie ARIA SearXNG nutzt

Wichtig:

- ARIA fuehrt keine Suchmaschine "intern" aus
- ARIA spricht die JSON-API von SearXNG an
- SearXNG bleibt ein separater Suchdienst im Stack

Das ist absichtlich so gebaut:

- die Websuche bleibt austauschbar
- der Suchdienst kann getrennt ueberwacht werden
- ARIA muss keine Suchlogik selbst hosten

## Warum SearXNG sinnvoll ist

Fuer ARIA bringt SearXNG einige klare Vorteile:

- self-hosted und kontrollierbar
- JSON-API passt gut zu ARIA
- Suchprofile lassen sich pro Zweck anpassen
- Treffer koennen mit Quellen in den Chat zurueckfliessen

## Typische Stellen in ARIA

Wenn du SearXNG in ARIA pruefen oder konfigurieren willst, sind diese Orte wichtig:

- `/connections`
- `/connections/types`
- `/config/connections/searxng`
- `/stats`

## Was du bei Problemen zuerst pruefen solltest

Wenn Websuche nicht funktioniert:

- ist der SearXNG-Dienst im Stack erreichbar?
- stimmt die Base-URL?
- antwortet die JSON-API?
- ist das Profil sauber gespeichert?

SearXNG ist fuer ARIA kein kleines Plugin, sondern die klare Suchschicht fuer Web-Recherche.
