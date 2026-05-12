# SearXNG in ARIA

Stand: 2026-05-12

SearXNG ist ARIAs separater self-hosted Suchdienst fuer Websuche. ARIA nutzt die JSON-API, nicht SearXNG-Code im App-Container.

## Wie ARIA SearXNG nutzt

- SearXNG laeuft als eigener Stack-Service
- Standard-URL im Stack: `http://searxng:8080`
- Profile in ARIA definieren Suchverhalten und Routing-Metadaten
- Chat-Antworten koennen Webquellen in den Details anzeigen

## Typische Nutzung

- `websuche ...`
- `recherchiere im web ...`
- spezifische Profile fuer YouTube, News, Buecher oder allgemeine Suche

## Profil-Felder

- Titel und Kurzbeschreibung
- Aliase und Tags
- Sprache
- SafeSearch
- Kategorien
- bevorzugte Engines
- Trefferzahl und Zeitbereich

## Abgrenzung zu RSS

RSS ist besser fuer kuratierte, wiederkehrende Quellen und News-Digests. SearXNG ist besser fuer offene Websuche. Beide koennen in Chat-Details Quellen ausweisen.

## Was bei Problemen zuerst pruefen

- laeuft der `searxng` Service im Stack?
- stimmt die Stack-URL?
- liefert die JSON-Suche Ergebnisse?
- hat das Profil passende Aliase/Tags?
- blockiert SafeSearch oder Kategorieauswahl zu stark?
