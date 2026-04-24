# ARIA — Alpha Build Log

Stand: 2026-04-22

Zweck:
- nachvollziehen, **was bereits in Alpha-Builds gelandet ist**
- festhalten, **was auf `dev` schon vorbereitet ist**
- Build-Versionen und inhaltliche Aenderungen zusammen sichtbar machen

## Bereits gebaut

### alpha167

- enthaelt den kompletten Fixstand bis einschliesslich `alpha166`
- Memory Map / Notes:
  - die `aria_notes_<user>`-Collection aus Qdrant erscheint jetzt sichtbar in der `Memory Map`
  - Notes bekommen dort einen eigenen Block `Notes-Collections` statt still unsichtbar im Backend zu bleiben
  - der Memory-Graph zeigt `Notizen` jetzt als eigenen Wissenszweig und verlinkt direkt zur Notizverwaltung `/notes`
- Users / Admin mode:
  - der kaputte Save-Pfad `/config/users/debug-save` ist korrigiert und funktioniert wieder
  - Hinweise wie `Admin mode off` fuehren jetzt direkt zum passenden Toggle auf `/config/users#admin-mode`
- Google Calendar:
  - die Schritt-Karten im Setup sind kompakter zusammengerueckt und visuell klarer als einzelne Schritte gerahmt
- Verifikation:
  - voller Testlauf: `634 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha167-local.tar`
- Release-Label:
  - `0.1.0-alpha167`

### alpha166

- enthaelt den kompletten Fixstand bis einschliesslich `alpha165`
- Notes / Notizen:
  - `/notes` startet jetzt standardmaessig im Board-Modus ohne sofort offenen Editor
  - Klick auf eine Notiz oder `Neu` oeffnet den Editor direkt im rechten Arbeitsbereich statt den User wieder nach unten scrollen zu lassen
  - frisch angelegte Ordner landen sichtbar im aktiven Ordnerkontext und wirken dadurch nicht mehr wie "verschwunden"
- Verifikation:
  - voller Testlauf: `631 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha166-local.tar`
- Release-Label:
  - `0.1.0-alpha166`

### alpha165

- enthaelt den kompletten Fixstand bis einschliesslich `alpha164`
- Notes / Notizen:
  - eigentliche Ursache fuer den weiterhin sichtbaren Editor-Overflow war nicht nur das Input-Sizing, sondern die Seitenbreite selbst
  - `notes-app-shell` orientiert sich jetzt sauber an der umgebenden `app-shell` statt mit einer eigenen Viewport-Breite nach rechts auszubrechen
  - `notes-explorer-shell` ist zusaetzlich auf `min-width: 0` und `max-width: 100%` gehaertet
  - dadurch sollte der rechte Notes-Arbeitsbereich in Safari und Firefox nicht mehr ueber den Rand hinausgedrueckt werden
- Verifikation:
  - voller Testlauf: `629 passed, 36 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha165-local.tar`
- Release-Label:
  - `0.1.0-alpha165`

### alpha164

- enthaelt den kompletten Fixstand bis einschliesslich `alpha163`
- Connection-Edit-Flow fuehlt sich auf `Beobachtete Webseiten` und den uebrigen Connection-Seiten jetzt deutlich direkter an:
  - `Neu` springt nicht mehr nur auf dieselbe Seite, sondern direkt in den Create-Bereich `#create-new`
  - Klicks auf bestehende Connection-Karten springen direkt in den Edit-Bereich `#manage-existing`
  - gerade auf schmaleren Screens muss man dadurch nicht mehr erst nach unten zum eigentlichen Formular suchen
- Notes / Notizen:
  - der rechte Editorbereich wurde fuer Safari und Firefox nochmals haerter gegen Layout-Overflow abgesichert
  - Titel-, Tag- und Inhaltsfelder erzwingen jetzt konsequenter `min-width: 0`, `max-width: 100%` und block-level Sizing innerhalb des Editor-Layouts
- Doku-Sweep:
  - die nutzernahe Produkt-/Wiki-/Help-Doku wurde fuer `Notizen`, `Beobachtete Webseiten` und `Google Calendar` nachgezogen
  - besonders die Trennung zwischen `Memory` und `Notizen` ist jetzt in den Help- und Wiki-Seiten klarer beschrieben
- Verifikation:
  - voller Testlauf: `629 passed, 35 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha164-local.tar`
- Release-Label:
  - `0.1.0-alpha164`

### alpha163

- enthaelt den kompletten Fixstand bis einschliesslich `alpha162`
- kleiner, aber wichtiger Notes-UI-Fix:
  - der rechte Arbeitsbereich der neuen Notes-Oberflaeche laeuft nicht mehr ueber den Rand hinaus
  - Editorrahmen und Eingabefelder bleiben jetzt geschlossen innerhalb des Panels, statt horizontal aus dem Layout zu kippen
  - dafuer wurden Breite, `min-width`, `box-sizing` und Overflow-Verhalten im Notes-Workspace gezielt gehaertet
- Verifikation:
  - voller Testlauf: `628 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha163-local.tar`
- Release-Label:
  - `0.1.0-alpha163`

### alpha162

- enthaelt den kompletten Fixstand bis einschliesslich `alpha161`
- Notes / Notizen wurden in diesem Build deutlich staerker zu einem eigenen Arbeitsbereich statt zu einem Memory-Anhaengsel:
  - die Notes-Seite haengt nicht mehr in der Memory-Subnavigation, sondern steht produktisch auf eigenen Fuessen
  - die alten oberen Health-/Qdrant-Kacheln sind verschwunden; Qdrant-Status gehoert fuer Notes nicht mehr prominent auf diese Seite
  - die Oberflaeche arbeitet jetzt eher wie ein kleiner Datei-Explorer mit linker Ordnernavigation, einem Zettel-Board aus Vorschaukarten und einem separaten Editorbereich auf der Arbeitsseite
  - Suchtreffer aus dem Notes-Index werden robuster auf echte lokale Notizen zurueckgemappt, auch wenn ein technischer Treffer stale IDs liefert
- zusaetzlich ist ein echter Skills-Regression-Fix drin:
  - `Core / System` und `Meine Skills` schalten sich beim Speichern nicht mehr gegenseitig aus, nur weil jeweils die andere Checkbox-Gruppe nicht im aktuellen Formular vorhanden war
- Verifikation:
  - voller Testlauf: `628 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha162-local.tar`
- Release-Label:
  - `0.1.0-alpha162`

### alpha161

- enthaelt den kompletten Fixstand bis einschliesslich `alpha160`
- Notes wachsen in diesem Build von einem ersten MVP zu einem deutlich nuetzlicheren Alltagswerkzeug:
  - normale Websuche kann jetzt passende Notes automatisch als Zusatzkontext mitziehen, statt Notes nur auf expliziten Notes-Pfaden zu verwenden
  - Notizen lassen sich im Chat natuerlicher anlegen, etwa ueber freie Formulierungen wie `halte fest ...` oder `notiere ...`
  - Webquellen bzw. einzelne URLs koennen direkt aus dem Chat als Notiz uebernommen werden; Titel, Kurzbeschreibung, Ordnerhinweise und Tags werden dabei automatisch vorgeschlagen bzw. mitgespeichert
  - Notes bleiben dabei bewusst `Markdown-first` und werden nur als abgeleiteter Suchindex in Qdrant gehalten; bei Aenderungen wird die betroffene Notiz vollstaendig neu gechunkt und reindexiert
- Verifikation:
  - voller Testlauf: `626 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha161-local.tar`
- Release-Label:
  - `0.1.0-alpha161`

### alpha160

- enthaelt den kompletten Fixstand bis einschliesslich `alpha159`
- Google-Calendar-Setup weiter geschaerft:
  - die Einrichtung ist jetzt als 6 klare Kacheln mit knappen, konkreten Arbeitsschritten aufgebaut
  - `Audience / Testnutzer` ist als eigener Schritt sichtbar statt in einem unklaren Verweis auf einen zweiten Link zu verschwinden
  - der OAuth-Playground-Teil beschreibt jetzt die genaue Reihenfolge fuer Scope, Authorize APIs und das Kopieren des Refresh-Tokens
- Verifikation:
  - voller Testlauf: `610 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha160-local.tar`
- Release-Label:
  - `0.1.0-alpha160`

### alpha159

- enthaelt den kompletten Fixstand bis einschliesslich `alpha158`
- Google-Calendar-Setup weiter auf echte Checklisten-Schritte verdichtet:
  - die Seite nutzt jetzt 5 knappe Kacheln statt laengerer Erklaertexte
  - pro Kachel steht nur noch, was konkret zu tun ist und welcher Link geoeffnet werden soll
  - der OAuth-/Refresh-Token-Flow ist dadurch deutlich scanbarer und naeher an einer echten Einrichtungs-Checkliste
- Verifikation:
  - voller Testlauf: `610 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha159-local.tar`
- Release-Label:
  - `0.1.0-alpha159`

### alpha158

- enthaelt den kompletten Fixstand bis einschliesslich `alpha157`
- Google-Calendar-Setup und Routing-Feinschliff fuer den naechsten Live-Test:
  - die Google-Calendar-Einrichtung fuehrt jetzt pro Karte klarer durch den naechsten konkreten Schritt (`Jetzt tun`) und erklaert direkt, wann zum folgenden Schritt gewechselt werden soll
  - die Links zu Google Cloud, OAuth Playground und Google Calendar bleiben am jeweils passenden Schritt statt als separate Linksammlung
  - natuerliche SSH-Disk-Checks wie `check mal die festplatte auf meinen dns server` werden jetzt auf `df -h` normalisiert, statt den ganzen Satz als Command auszufuehren
  - `df -h` gilt im Dry-Run-/Confirm-Pfad jetzt als sicherer Standard-Read-Only-Command
- Verifikation:
  - voller Testlauf: `610 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha158-local.tar`
- Release-Label:
  - `0.1.0-alpha158`

### alpha157

- enthaelt den kompletten Fixstand bis einschliesslich `alpha156`
- letzter UI-Feinschliff vor dem Google-Livetest:
  - `/config/operations` zeigt `Updates` jetzt als ersten Block ganz oben
  - die wenig hilfreiche Leerlauf-Zeile `Aktueller Schritt` ist dort entfernt; auf den echten Update-Live-Seiten bleibt sie weiter sichtbar
  - die Google-Calendar-Setup-Seite nutzt jetzt die Schritt-Kacheln selbst als Linktraeger, statt dieselben Google-Links noch einmal als separate Liste ueber dem Flow zu wiederholen
- Verifikation:
  - voller Testlauf: `605 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha157-local.tar`
- Release-Label:
  - `0.1.0-alpha157`

### alpha156

- enthaelt den kompletten Fixstand bis einschliesslich `alpha155`
- weiterer Public-Release-Readiness-Schnitt vor dem naechsten oeffentlichen Stand:
  - `aria/web/config_routes.py` liegt jetzt unter `1000` Zeilen; der verbleibende Profil-/Embedding-/Sample-Helper-Block lebt in `aria/web/config_profile_helpers.py`
  - `aria/main.py` bleibt auf dem schlankeren Bootstrapping-Kurs unter `1200` Zeilen
  - die alte Moduloberflaeche fuer Tests und Monkeypatches blieb dabei bewusst stabil
- Google-Calendar-Readiness und der produktnahe Public-Smoke-Stand sind mit in diesem Build
- Verifikation:
  - voller Testlauf: `605 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha156-local.tar`
- Release-Label:
  - `0.1.0-alpha156`

### alpha153

- enthaelt den kompletten Fixstand bis einschliesslich `alpha152`
- weiterer sauberer Architektur-Schnitt rund um Routing-/Web-/Connection-Helfer:
  - die verbleibenden Connection-Reader und die per-Typ-Connection-Context-Builder leben jetzt in
    - `aria/web/connection_reader_helpers.py`
    - `aria/web/connection_context_helpers.py`
    statt weiter in `aria/web/config_routes.py`
  - `aria/web/config_routes.py` verliert damit nochmals spuerbar fachliche Helper-Masse und bleibt staerker bei Route-/Wiring-Verantwortung
  - die bereits gezogenen Chat-/Session-/Runtime-/Connection-Slices bilden jetzt deutlich konsistenter denselben Web-Layer statt weiterer Inline-Cluster in `main.py` und `config_routes.py`
- Routing-/Planner-/Resolver-Cleanup aus der laufenden Alpha-Linie ist mit in diesem Stand:
  - Chat und Workbench teilen sich denselben Produktpfad fuer Routing, Planner, Payload und Guardrails
  - stale Qdrant-Routing-Indizes werden fuer Nutzer selbstheilender behandelt
  - bestaetigungspflichtige Outbound-Aktionen bleiben kontrolliert ueber `ask_user`
  - `CapabilityRouter` und Routing-Lexikon wurden weiter auf gemeinsame Quellen zusammengezogen
- Verifikation:
  - voller Testlauf: `577 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha153-local.tar`
- Release-Label:
  - `0.1.0-alpha153`

### alpha152

- enthaelt den kompletten Fixstand bis einschliesslich `alpha151`
- Routing-/Planner-/Guardrail-Konsistenz jetzt wirklich als gemeinsamer Produktpfad:
  - der Live-Chat benutzt nicht mehr die alten separaten Live-Ausfuehrungspfade fuer `ssh` und generische Capability-Aktionen
  - Chat und Workbench teilen sich jetzt fuer unterstuetzte Verbindungsarten dieselbe Kette aus:
    - Routing
    - Action-Planer
    - Payload-Bau
    - Guardrail / Confirm
    - Execution Preview
  - die fruehere Inkonsistenz zwischen Routing-Testbench und echtem Chat-Verhalten wird dadurch deutlich reduziert
  - bestaetigungspflichtige Outbound-Aktionen wie `discord`, `webhook`, `email` und `mqtt` laufen jetzt konsistent ueber `ask_user` statt ueber uneinheitliche Altpfade
  - Qdrant-Routing im Live-Chat respektiert wieder Feature-Flag, Stale-Index-Checks und die gleichen Debug-/Detailhinweise wie der neue Resolver
  - Kontextfaelle wie `im gleichen Ordner` und Single-Profile-Faelle wurden auf der neuen Kette wieder sauber hergestellt
- Verifikation:
  - Routing-/Planner-/Pipeline-/Chat-Regressionssuite gruen
  - voller Testlauf: `570 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha152-local.tar`
- Release-Label:
  - `0.1.0-alpha152`

### alpha151

- enthaelt den kompletten Fixstand bis einschliesslich `alpha150`
- Routing-/Planner-Integration ist jetzt nicht mehr nur Workbench-Dry-run, sondern sauber bis in den Live-Chat zusammengezogen:
  - Chat und Workbench teilen sich jetzt fuer unterstuetzte Verbindungstypen dieselbe Routing-/Action-/Payload-/Guardrail-Kette
  - `allow`, `ask_user` und `block` gelten damit nicht mehr nur in der Testbench, sondern auch im echten Chat-Verhalten
  - bestaetigungspflichtige Aktionen koennen im Chat kontrolliert ueber `bestaetige aktion <token>` freigegeben werden
  - regelbasierte Custom-Skills behalten bewusst Vorrang, waehrend der neue gemeinsame Resolver Templates und verbindungsgebundene Skills konsistenter zusammenfuehrt
- Verifikation:
  - Routing-/Pipeline-/Chat-Regressionssuite gruen
  - breiter UI-/Session-/Update-Sanity-Block gruen
  - voller Testlauf: `562 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha151-local.tar`
- Release-Label:
  - `0.1.0-alpha151`

### alpha150

- enthaelt den kompletten Fixstand bis einschliesslich `alpha149`
- letzte Konsistenz- und Theme-Politur vor dem naechsten groesseren Produktblock:
  - Bereichstitel auf den grossen Domain-/Config-Seiten laufen jetzt wieder konsistent mit Icon, statt gemischt mit und ohne Symbol aufzutreten
  - `Aussehen & Theme` nutzt Hintergruende jetzt komplett dateibasiert:
    - alle Optionen kommen direkt aus `background-*`-Dateien in `aria/static/`
    - keine fest verdrahteten Sprachdatei-Eintraege mehr fuer Background-Namen
    - neue Bilder tauchen damit automatisch in der UI auf, solange sie der Naming-Convention folgen
  - die Label-Generierung fuer dynamische Hintergruende ist lesbarer geworden:
    - `8-Bit Arcade`
    - `AI Lobby`
    - `ARIA Thinking`
  - doppelte Background-Eintraege wurden beseitigt, indem die bisherige Mischlogik aus festen und dynamischen Optionen durch eine einheitliche Datei-Quelle ersetzt wurde
- Verifikation:
  - Error-/Config-Regressionen gruen
  - voller Testlauf: `554 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha150-local.tar`
- Release-Label:
  - `0.1.0-alpha150`

### alpha149

- enthaelt den kompletten Fixstand bis einschliesslich `alpha148`
- letzte Konsistenz- und Produktfluss-Politur vor dem naechsten groesseren Themenblock:
  - `Gedächtnis`-Karten wurden mikrotypografisch sauberer ausgerichtet:
    - `Eigene Memory erfassen`
    - `Dokumente importieren`
    - `Nächste Schritte`
    nutzen jetzt dasselbe stabile Icon-/Titel-/Badge-Raster
  - auffaellige Icon-Unstimmigkeiten wurden bereinigt:
    - `Gedächtnis-Explorer` zeigt wieder das passende `Gedächtnis`-Icon statt eines fachfremden Symbols
    - Dokument-Importe nutzen konsistent ein `Upload`-Icon
  - die Dev-/Produktlinie bleibt damit auch im kleinen Detail deutlich ruhiger und konsistenter
- Verifikation:
  - Gedächtnis-/Config-Regressionen gruen
  - voller Testlauf: `554 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha149-local.tar`
- Release-Label:
  - `0.1.0-alpha149`

### alpha148

- enthaelt den kompletten Fixstand bis einschliesslich `alpha147`
- letzte Konsistenz- und Mobil-Politur vor dem naechsten groesseren Produktblock:
  - `/updates` haengt jetzt sichtbar unter `Einstellungen > Betrieb & Transfer` und nutzt denselben Settings-Kopf wie die restlichen Config-Unterseiten
  - `Benutzer` bleibt nur noch unter `Einstellungen > Zugriff & Sicherheit`; das App-Menue selbst bleibt dadurch schlanker
  - `Hilfe`, `Produkt-Info`, `Updates` und `Lizenz` teilen sich jetzt denselben ruhigen Doku-Rahmen mit konsistentem Header-/Pill-Menue und dunklerem Inhalts-Akzent fuer bessere Lesbarkeit
  - Primary Actions auf Config-Seiten wurden vereinheitlicht: zentrale Speichern-/Ausfuehren-Aktionen wirken ruhiger, sind besser lesbar gruppiert und stehen klarer getrennt von destruktiven Aktionen
  - der globale Zurueck-Pfeil wurde aus der UI entfernt; die Navigation ist inzwischen stark genug und der wartungsintensive Sonderpfad faellt damit weg
  - die Chat-Arbeitsflaeche ist auf kleinen Screens jetzt dynamischer:
    - leerer/frischer Chat startet kompakter, damit Composer und Tool-Box auf dem iPhone frueher sichtbar bleiben
    - mit echtem Verlauf waechst die Flaeche wieder in eine komfortable Scroll-Hoehe hinein
- Verifikation:
  - Help-/Update-/Config-/Session-/Chat-Regressionen gruen
  - voller Testlauf: `554 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha148-local.tar`
- Release-Label:
  - `0.1.0-alpha148`

### alpha147

- enthaelt den kompletten Fixstand bis einschliesslich `alpha146`
- die neue UI-Linie ist jetzt auch visuell ueber die Hauptbereiche zusammengezogen:
  - eine gemeinsame dunkelgruene Buehne umrahmt jetzt die eigentlichen Seitenbereiche, waehrend die funktionalen Elemente weiterhin frei und leicht wirken
  - `Gedächtnis` war die Referenz, danach wurde derselbe Rahmen konsequent auf `Fähigkeiten`, `Verbindungen`, `Einstellungen`, `Statistiken` und den Doku-Bereich ausgerollt
- dadurch wirkt die Oberflaeche jetzt deutlich konsistenter:
  - weniger Flickwerk zwischen den Bereichen
  - mehr klare Seitenbuehne ohne Rueckfall in schwere Kachel-in-Kachel-Optik
- Verifikation:
  - Memory-/Skill-/Config-/Help-/Stats-Regressionen gruen
  - voller Testlauf: `554 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha147-local.tar`
- Release-Label:
  - `0.1.0-alpha147`

### alpha146

- enthaelt den kompletten Fixstand bis einschliesslich `alpha145`
- GUI-Re-Thinking jetzt als zusammenhaengender Hauptschnitt gebaut:
  - `Gedächtnis`, `Fähigkeiten`, `Verbindungen` und `Einstellungen` sind jetzt klarer als ruhige Hubs und Unterseiten organisiert
  - der neue Clean-Look reduziert schwere Trägerflächen und laesst die eigentlichen Funktionselemente bewusster stehen
  - `Statistiken` wurde optisch beruhigt, ohne die bestehende Einzelseiten-Logik zu zerlegen
- Doku-/Hilfebereich deutlich sauberer und konsistenter:
  - `Hilfe` ist schlanker aufgebaut und zeigt die eigentlichen Hilfetexte schneller
  - neue Seite `Lizenz` mit ARIA-, Qdrant- und SearXNG-Lizenzhinweisen
  - Qdrant und SearXNG sind als sichtbare Help-Themen praesent, ohne das obere Help-Menü zu überladen
- weitere UI-Details nachgezogen:
  - `/config/users` im Clean-Design
  - `/memories/config` mit klarer getrennten Abschluss-Aktionen
  - `/connections` wieder mit gemeinsam genutztem Live-Status-Block wie in `Statistiken`
- Verifikation:
  - Help-/Config-/Memory-/Skill-/Session-/Stats-/Update-Regressionen gruen
  - voller Testlauf: `554 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha146-local.tar`
- Release-Label:
  - `0.1.0-alpha146`

### alpha145

- enthaelt den kompletten Fixstand bis einschliesslich `alpha144`
- Gedächtnis-Übersicht weiter in die ruhigere Explorer-Richtung geschoben:
  - `Aktionen` und `Tools` stehen jetzt direkt unter der Übersichts-Kachel, noch vor dem Graphen
  - `/memories` nutzt dafür eine leichtere Flächenwirkung statt der schweren Vollflächen-Optik
  - der Stand ist bewusst als Sicht-Build gedacht, damit der neue Stil live gegen das Matrix-Theme beurteilt werden kann
- Verifikation:
  - Gedächtnis-Routen-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha145-local.tar`
- Release-Label:
  - `0.1.0-alpha145`

### alpha144

- enthaelt den kompletten Fixstand bis einschliesslich `alpha143`
- Connections-Hub wieder mit dem richtigen operativen Ueberblick:
  - der Live-Status aller konfigurierten Verbindungen ist jetzt wieder direkt auf `/connections` sichtbar
  - dafuer wird derselbe Status-Block wie auf `/stats` wiederverwendet, statt eine zweite Sonderdarstellung einzufuehren
  - die Verbindungs-Hauptseite fuehlt sich dadurch wieder vollstaendiger und nuetzlicher an
- Verifikation:
  - Config-/Update-/Session-Regressionen gruen
  - voller Testlauf: `steht nach Build-Lauf fest`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha144-local.tar`
- Release-Label:
  - `0.1.0-alpha144`

### alpha143

- enthaelt den kompletten Fixstand bis einschliesslich `alpha142`
- GUI-Feinschliff und Sprachkonsistenz weiter beruhigt:
  - die deutschen Hauptbegriffe sind jetzt in der sichtbaren UI klarer gezogen: `Gedächtnis`, `Fähigkeiten`, `Verbindungen`
  - `/help` ist deutlich schlanker aufgebaut und zeigt den eigentlichen Hilfetext schneller und klarer
  - das Inhaltsverzeichnis der Hilfe wirkt jetzt eher wie eine ruhige Dokumentnavigation statt wie eine zweite Landingpage
- Einordnung:
  - guter Zwischenstand fuer das bisherige GUI-Re-Thinking
  - die Hauptdomänen wirken jetzt deutlich konsistenter und weniger überladen
- Verifikation:
  - Help-/I18n-/Config-/Memory-/Skill-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha143-local.tar`
- Release-Label:
  - `0.1.0-alpha143`

### alpha142

- enthaelt den kompletten Fixstand bis einschliesslich `alpha141`
- Feinschliff fuer die Hauptseiten-Informationsarchitektur:
  - `/connections` hat keine nutzlose Selbst-Referenz im Kopf mehr
  - die Uebersichtskarten auf `/connections` sind jetzt echte Einstiege zu Verbindungstypen, SearXNG und Samples
  - `/config` zeigt in den Statuskarten oben jetzt die eigentlichen Werte als primaere Zeile
  - die erklaerenden Beschreibungen auf `/config` sitzen dadurch ruhiger und konsistenter in der Meta-Zeile wie auf den anderen Hauptseiten
- Verifikation:
  - Config-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha142-local.tar`
- Release-Label:
  - `0.1.0-alpha142`

### alpha141

- enthaelt den kompletten Fixstand bis einschliesslich `alpha140`
- Hauptseiten visuell weiter harmonisiert:
  - `/skills` hat jetzt oben eine echte Uebersicht mit kompakten Statuskarten statt nur Titel und Fliesstext
  - `/connections` wirkt im Intro ruhiger und integriert sich besser in den restlichen Seitenstil
  - `/config` nutzt weiter denselben Header-Stil, aber die Navigation springt jetzt direkt in die jeweils geoeffnete Zielsektion
  - die nutzlose `Einstellungen`-Kachel in der Settings-Navigation ist entfernt
- Verifikation:
  - Config-/Skill-/Session-Regressionen gruen
  - voller Testlauf: `steht nach Build-Lauf fest`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha141-local.tar`
- Release-Label:
  - `0.1.0-alpha141`

### alpha140

- enthaelt den kompletten Fixstand bis einschliesslich `alpha139`
- App-Menue und Settings-Hub weiter geschaerft:
  - `Einstellungen` steht im App-Menue jetzt bewusst vor `Statistiken`
  - `/config` hat nun dieselbe klare Kopf-/Anchor-Struktur wie `Memories`, `Skills` und `Connections`
  - die Bereiche `Uebersicht`, `Intelligenz`, `Persoenlichkeit & Stil`, `Zugriff & Sicherheit`, `Betrieb & Transfer` und `Workbench` sind direkt oben anspringbar
- Verifikation:
  - Config-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha140-local.tar`
- Release-Label:
  - `0.1.0-alpha140`

### alpha139

- enthaelt den kompletten Fixstand bis einschliesslich `alpha138`
- Navigation weiter vereinfacht:
  - `Chat` ist nicht mehr als eigener Punkt im App-Menue sichtbar
  - das ARIA-Logo bleibt der direkte Rueckweg zur Startseite
- Connections-Hub an die Informationsarchitektur von `Memories` und `Skills` angeglichen:
  - `/connections` hat jetzt oben dieselbe kompakte Navigation im Kachel-/Pill-Stil
  - die Navigation springt auf Anchors innerhalb derselben Seite
  - damit fuehlen sich die drei Hauptdomänen `Memories`, `Skills` und `Connections` nun deutlich einheitlicher an
- Verifikation:
  - Config-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha139-local.tar`
- Release-Label:
  - `0.1.0-alpha139`

### alpha138

- enthaelt den kompletten Fixstand bis einschliesslich `alpha137`
- Update-Seite weiter geschaerft:
  - `Kontrolliertes Update` ist jetzt die primaere Funktion auf `/updates`
  - der Bereich ist nicht mehr als eingeklapptes Detail versteckt, sondern als offene Primärkarte direkt oben sichtbar
  - Status, Start-Button und Log sind dadurch sofort im Fokus
- Skill-Seite weiter an die Memory-Informationsarchitektur angeglichen:
  - `/skills` hat jetzt oben eine Navigation im selben Stil wie `Memories`
  - die Navigation springt auf Anchors innerhalb derselben Seite
  - Reihenfolge jetzt bewusst: `Skill starten`, `Meine Skills`, `Core / System`, `Vorlagen`
  - `Core / System` steht im Hauptfluss vor den Sample-Skills
  - `Mitgelieferte Sample-Skills` bleiben standardmaessig eingeklappt
- Verifikation:
  - Update-/Skill-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha138-local.tar`
- Release-Label:
  - `0.1.0-alpha138`

### alpha137

- enthaelt den kompletten Fixstand bis einschliesslich `alpha136`
- Skill-Bereich als klarerer Hub ueberarbeitet:
  - `/skills` ist jetzt staerker entlang der eigentlichen Nutzerarbeit geschnitten
  - `Meine Skills` stehen zuerst
  - ein eigener Block `Skill starten` macht Wizard und JSON-Import sofort sichtbar
  - `Mitgelieferte Sample-Skills` leben klar getrennt als Vorlagen-Bibliothek
  - `Core / System` ist weiter unten einsortiert und ueberdeckt den eigentlichen Nutzerfluss nicht mehr
- Sample-Skills verhalten sich jetzt robust eingeklappt:
  - die Karten basieren weiter auf `<details>`
  - der Inhaltsbereich wird aber zusaetzlich explizit verborgen, solange die Karte nicht geoeffnet ist
  - damit bleibt das Einklappen auch dann konsistent, wenn ein Browser `<details>` eigenwillig rendert
- Memory-Graph nachgezogen:
  - Detail-Knoten uebernehmen jetzt ihr echtes Typ-Icon statt pauschal nur das Memory-Symbol zu zeigen
- Verifikation:
  - Skill-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha137-local.tar`
- Release-Label:
  - `0.1.0-alpha137`

### alpha136

- enthaelt den kompletten Fixstand bis einschliesslich `alpha135`
- Qdrant-Zugriff im Memory-Setup weiter verbessert:
  - der Dashboard-Einstieg kann jetzt in einer Benutzeraktion gleichzeitig das Qdrant-Dashboard oeffnen und den API-Key in die Zwischenablage legen
  - wenn kein API-Key vorhanden ist, oeffnet derselbe Einstieg einfach nur das Dashboard
  - der Clipboard-Fallback fuer lokale/insecure Browser-Kontexte bleibt dabei aktiv
- Verifikation:
  - fokussierte Memory-/Config-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha136-local.tar`
- Release-Label:
  - `0.1.0-alpha136`

### alpha135

- enthaelt den kompletten Fixstand bis einschliesslich `alpha134`
- Memory-Bereich in der Bedienlogik weiter entschaerft:
  - auf `/memories/config#qdrant-access` ist der `Qdrant API Key` jetzt standardmaessig verborgen
  - der Copy-Button fuer URL und API-Key nutzt jetzt neben der Clipboard-API auch einen robusten Fallback fuer lokale/insecure Browser-Kontexte
  - auf `/memories/explorer` liegen keine Erfassungs-/Import-Aktionen mehr zwischen Suche und Browse-Flow
  - `Eigene Memory erfassen` und `Dokumente importieren` leben jetzt passend auf der `Memory-Uebersicht`
  - Create-/Upload-Aktionen springen von dort nach erfolgreicher Ausfuehrung auch wieder sauber auf die Uebersicht zurueck
- Verifikation:
  - fokussierte Memory-/Config-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha135-local.tar`
- Release-Label:
  - `0.1.0-alpha135`

### alpha134

- enthaelt den kompletten Fixstand bis einschliesslich `alpha133`
- Menue-Trigger weiter verbessert:
  - statt der drei Punkte nutzt das kompakte App-Menue jetzt ein Gear-/Settings-Icon
  - der Trigger signalisiert damit klarer, dass dort Bereiche, Optionen und Systemaktionen liegen
- Memory-Uebersicht weiter beruhigt und nuetzlicher gemacht:
  - auf `/memories` wird unten nicht mehr die Unterseiten-Navigation wiederholt
  - stattdessen zeigt die Seite jetzt direkt eine integrierte `Memory-Graph`-Vorschau
  - im `Tools`-Block gibt es neben dem Export jetzt auch einen klaren Einstieg zu `Qdrant-Zugriff`
  - dieser Einstieg fuehrt direkt auf `/memories/config#qdrant-access`, wo URL, API-Key und Dashboard-Link an einer Stelle fuer Copy/Paste liegen
- Verifikation:
  - fokussierte Memory-/Config-/Session-Regressionen gruen
  - voller Testlauf: `547 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha134-local.tar`
- Release-Label:
  - `0.1.0-alpha134`

### alpha133

- enthaelt den kompletten Fixstand bis einschliesslich `alpha132`
- Hauptnavigation wieder bewusst beruhigt:
  - die sichtbare Desktop-Leiste mit allen Hauptbereichen wurde wieder entfernt
  - stattdessen nutzt ARIA jetzt wieder ein einzelnes kompaktes App-Menue oben rechts
  - der Chat bleibt dadurch oben ruhiger und wird nicht von einer breiten Navigationsleiste ueberlagert
- dabei bleibt die verbesserte Informationsarchitektur erhalten:
  - `Chat`, `Memories`, `Skills`, `Connections`, `Statistiken`, `Einstellungen` und `Hilfe` leben weiter in einer klareren Reihenfolge innerhalb des Menues
  - aktive Bereiche werden im Menue hervorgehoben
  - Benutzer-/Admin-/Logout-Aktionen bleiben sauber von den eigentlichen App-Bereichen getrennt
- Verifikation:
  - fokussierte Config-/Memory-/Skill-/Session-Regressionen gruen
  - voller Testlauf: `547 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha133-local.tar`
- Release-Label:
  - `0.1.0-alpha133`

### alpha132

- enthaelt den kompletten Fixstand bis einschliesslich `alpha131`
- Hauptnavigation als klarere Produktnavigation umgebaut:
  - auf Desktop sind jetzt die Kernbereiche sichtbar statt hinter einem generischen Menue zu verschwinden
  - primaere Navigation: `Chat`, `Memories`, `Skills`, `Connections`
  - sekundaere Navigation: `Statistiken`, `Einstellungen`, `Hilfe`
  - Benutzer-/Admin-/Logout-Aktionen leben separat im Account-Menue
  - auf Mobile bleibt ARIA bewusst kompakt ueber das Account-/Menue-Dropdown bedienbar
- Domainen und Hubs weiter geschaerft:
  - `Connections` hat jetzt eine echte Hauptseite unter `/connections` statt nur als Anker in `Einstellungen`
  - `Einstellungen` ist als System-/Admin-Hub neu geordnet und zeigt Connections nicht mehr doppelt
  - `Updates` bleibt eine einzige Seite unter `/updates`, ist aber jetzt sinnvoll von `Hilfe` und `Einstellungen` aus erreichbar
- weitere UI-Beruhigung in den Kernbereichen:
  - `Memory-Setup` zeigt Qdrant-Zugriff, URL, API-Key und Dashboard-Link jetzt nur noch an einer zentralen Stelle
  - die mitgelieferten Sample-Skills auf `/skills` sind standardmaessig eingeklappt und erschlagen die Seite nicht mehr
- Verifikation:
  - fokussierte Config-/Memory-/Skill-/Session-Regressionen gruen
  - voller Testlauf: `547 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha132-local.tar`
- Release-Label:
  - `0.1.0-alpha132`

### alpha131

- enthaelt den kompletten Fixstand bis einschliesslich `alpha130`
- Memory-IA und Memory-UI weiter beruhigt:
  - `Memories` ist jetzt der echte Hub unter `/memories`
  - der eigentliche Explorer lebt auf `/memories/explorer`
  - alte Explorer-Links mit `/memories?type=...` werden sauber auf den neuen Explorer-Pfad umgeleitet
  - alle Memory-Seiten nutzen jetzt eine gemeinsame lokale Navigation fuer `Uebersicht`, `Explorer`, `Map` und `Setup`
  - Qdrant-Dashboard-/API-Key-Kram ist aus Uebersicht und Map entfernt und lebt nur noch im `Memory-Setup`
- Memory-Uebersicht und Memory-Map optisch nachgeschaerft:
  - Uebersicht zeigt jetzt klare Status-Laempchen fuer Qdrant, aktive Collection, User-Memory, Dokumente und Auto-Memory
  - Explorer hat einen ruhigeren Kopfbereich mit Fokus-/Treffer-Zusammenfassung
  - Memory-Map hat jetzt einen klareren Hero-Bereich, konsolidierte Health-Karten und wertigere Abschnitts-Header
  - Collection- und Routing-Karten wirken kompakter und bewusster gestaltet
- Verifikation:
  - fokussierte Memory-/Config-/Session-Regressionen gruen
  - voller Testlauf: `544 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha131-local.tar`
- Release-Label:
  - `0.1.0-alpha131`

### alpha130

- enthaelt den kompletten Fixstand bis einschliesslich `alpha129`
- Routing-Testbench sauber ausgelagert:
  - die komplette Dry-run-Testbench lebt jetzt als eigene Workbench-Seite unter `/config/workbench/routing`
  - `/config/routing` konzentriert sich wieder auf Routing-Index, Live-Qdrant-Settings und Routing-/Memory-Regeln
  - alte Deep-Links mit `routing_query=...` auf `/config/routing` werden sauber auf die neue Workbench umgeleitet
- Memory-Navigation vereinheitlicht:
  - neuer zentraler Hub unter `/memories/overview`
  - Hauptmenue `Memories` fuehrt jetzt auf diese Uebersichtsseite
  - Memory-Map, Memory-Setup sowie routingnahe Memory-/Skill-Trigger liegen dort jetzt gesammelt an einem Ort
  - doppelte Memory-Einstiegspunkte unter `Einstellungen` wurden entfernt
- kleine UI-Nachschaerfung:
  - `Memory Map` und `Memory-Setup` auf `/memories` nutzen jetzt ebenfalls Icons
- Verifikation:
  - fokussierte Config-/Memory-/Skill-/Session-Regressionen gruen
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha130-local.tar`
- Release-Label:
  - `0.1.0-alpha130`

### alpha129

- enthaelt den kompletten Fixstand bis einschliesslich `alpha128`
- Routing-Dry-run robuster gemacht:
  - der bounded `Action / Skill`-Planner faellt bei leicht abweichenden LLM-Kandidatennamen nicht mehr mit `Kein Treffer` aus
  - stattdessen wird die LLM-Auswahl innerhalb der bounded Menge normalisiert oder kontrolliert auf den klaren heuristischen Kandidaten zurueckgefuehrt
  - dadurch laufen `Payload dry-run`, `Guardrail / Confirm dry-run` und `Final execution preview` bei natuerlichen SSH-Health-Fragen wieder sauber durch
- Memory-Map visuell nachgeschaerft:
  - Root-, Typ- und Collection-Knoten sind kompakter
  - Collections/Memory-Knoten nutzen jetzt ikonischere Darstellungen statt schwerer Rahmen
  - die Map braucht weniger Breite und wirkt ruhiger/lesbarer
- Verifikation:
  - fokussierte Planner-/Routing-/Memory-Regressionen gruen
  - voller Testlauf: `538 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha129-local.tar`
- Release-Label:
  - `0.1.0-alpha129`

### alpha128

- enthaelt den kompletten Fixstand bis einschliesslich `alpha127`
- Dry-run-Pfad in der Routing-Testbench jetzt end-to-end sichtbar:
  - `Action / Skill dry-run` waehlt zwischen sicheren Templates und passenden Custom Skills
  - `Payload dry-run` zeigt konkrete Eingaben wie SSH-Command, Dateipfad oder Nachrichtenvorschau
  - `Guardrail / Confirm dry-run` zeigt, ob ARIA direkt ausfuehren, nachfragen oder blocken wuerde
  - `Final execution preview` fasst Ziel, Capability und den naechsten sicheren Schritt zusammen
- Sicherheits-/Zugriffsgrenzen nachgezogen:
  - geschuetzte HTML-Seiten leiten ohne Session weiter korrekt auf `/login`
  - `/updates` bleibt absichtlich oeffentlich sichtbar
  - Managed-Update-Aktionen bleiben ohne Login/Admin weiter gesperrt
- Verifikation:
  - fokussierte Dry-run- und Auth-Regressionen gruen
  - voller Testlauf: `537 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha128-local.tar`
- Release-Label:
  - `0.1.0-alpha128`

### alpha127

- enthaelt den kompletten Fixstand bis einschliesslich `alpha126`
- UI-/Icon-Welle weitergezogen:
  - `Skills`, `Memories`, `Memory Map`, `Stats`, `RSS Connections`, `Import / Export`, Connection-Navigation und Kontext-Hilfe nutzen jetzt deutlich mehr ikonische Aktionen statt schwerer Textbuttons
  - betroffen sind vor allem Back-, Edit-, Delete-, Refresh-, Import-/Export- und Routing-Aktionen
  - im Skill-Wizard sind auch `Verbindungen verwalten`, Speichern/Loeschen und der Ruecksprung kompakter und konsistenter
- Mobile-/Scanbarkeit verbessert:
  - zentrale Actions auf dichten Admin-Seiten sind schneller erfassbar
  - Memories-Suche, Kontext-Rollup und `Mehr dazu` auf Help-Karten sind jetzt ebenfalls iconisiert
  - die Routing-/Pricing-Admin-Shortcuts in `Stats` folgen jetzt derselben Aktionssprache
- Verifikation:
  - fokussierte Template-/UI-Regressionen gruen
  - voller Testlauf: `532 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha127-local.tar`
- Release-Label:
  - `0.1.0-alpha127`

### alpha126

- enthaelt den kompletten Fixstand bis einschliesslich `alpha125`
- Routing-/Planner-Dry-run weiter verfeinert:
  - finale Action-Entscheidungen und Kandidaten zeigen jetzt eine kompakte Summary-Zeile in menschlicherer Satzform
  - Beispiele:
    - `Template: Gesundheitscheck via SSH-Befehl auf ssh/pihole1`
    - `Template: Datei lesen auf sftp/mgmt`
  - die Summary unterdrueckt doppelte Begriffe wie `Datei lesen`, wenn Intent und Capability ohnehin dasselbe meinen
- Routing-Testbench kompakter gemacht:
  - die finale Action-Karte und die Kandidatenliste zeigen weniger redundante Detailzeilen
  - Candidate type und Capability werden nicht mehr doppelt separat wiederholt, wenn die Summary sie schon traegt
  - uebrig bleiben die relevanten Review-Daten wie Score, State, Preview, Inputs, Rueckfrage und Beispiel-Prompt
- Review-/Qualitaetsstand:
  - fokussierte Planner-/Routing-Regressionen gruen
  - voller Testlauf: `531 passed`
  - kurzer Diff-/Selbstreview vor dem Build: keine blockierenden Findings
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha126-local.tar`
- Release-Label:
  - `0.1.0-alpha126`

### alpha125

- enthaelt den kompletten Fixstand bis einschliesslich `alpha124`
- Routing-Hints / Connection-Metadaten:
  - gemeinsamer Helfer `aria/core/routing_hints.py` fuehrt Skill-Keyword- und Connection-Metadaten-Hints jetzt zusammen
  - SSH- und SFTP-Profile koennen Routing-Metadaten beim Speichern jetzt automatisch aus `service_url` ergaenzen, wenn Titel/Beschreibung/Aliase/Tags noch leer oder duenn sind
  - vorhandene Nutzerwerte bleiben fuehrend und werden nicht blind ueberschrieben
- Skill-Wizard weiter entschaerft:
  - `Skill type` mit gefuehrten Defaults fuer `Health Check`, `Monitor`, `Notify`, `Fetch`, `Sync`
  - Simple-Mode setzt Kategorie, Beschreibung und erste Step-Defaults jetzt serverseitig, nicht nur per UI
  - Simple-Mode zeigt je Skill-Typ nur noch sinnvolle Step-Typen
  - passende Folge-Schritte koennen im Simple-Mode direkt per Klick hinzugefuegt werden
  - Hauptverbindung wird im Simple-Mode jetzt ebenfalls gefuehrt und kann aus vorhandenen Connections direkt in den ersten Step uebernommen werden
- Scope bewusst klein gehalten:
  - kein Umbau des Skill-Manifests
  - keine Runtime-/Executor-Aenderung
  - keine Live-Aktivierung neuer Planner-/Intent-Logik
- Tests:
  - fokussierte Regressionen fuer Config-Routen sowie Skill-Wizard / Custom-Skills / Sample-Skills gruen
  - voller Testlauf: `510 passed`
- Release-Label:
  - `0.1.0-alpha125`

### alpha124

- enthaelt den kompletten Fixstand bis einschliesslich `alpha123`
- Skill-Wizard erster Entschlackungs-Schnitt:
  - neuer `Simple Skill` / `Advanced Skill`-Modus
  - `Simple` ist jetzt der gefuehrte Standardpfad
  - `Advanced` blendet Rohschritte, Metadaten und Feintuning wieder ein
  - pro Step werden nur noch die zum gewaehlten Step-Typ passenden Felder gezeigt
  - der Wizard-Modus bleibt nach dem Speichern erhalten
- Scope bewusst klein gehalten:
  - keine Aenderung am Skill-Manifest-Format
  - keine Runtime-/Executor-Umstellung
  - vorhandene komplexe Skills sollen weiter funktionieren
- Tests:
  - Skill-Wizard-, Custom-Skill- und Sample-Skill-Regressionen gruen
  - voller Testlauf: `507 passed`
- Release-Label:
  - `0.1.0-alpha124`

### alpha123

- enthaelt den kompletten Fixstand bis einschliesslich `alpha122`
- Routing-Testbench erweitert:
  - neuer Debug-Schalter, um den `LLM router dry-run` ohne deterministischen Hint zu testen
  - dadurch ist `Qdrant + LLM` isoliert beurteilbar, ohne das Live-Routing zu veraendern
- Routing-/Admin-Integration:
  - `/config/routing`
  - `/config/routing-index/test`
  - unterstuetzen jetzt den Debug-Modus fuer `Qdrant + LLM only`
- Tests:
  - Routing-Admin, Config-Routing und Pipeline-Regressions fuer den neuen Debug-Schalter gruen
- Release-Label:
  - `0.1.0-alpha123`

### alpha122

- enthaelt den kompletten Fixstand bis einschliesslich `alpha121`
- LLM-Routing erster sicherer Schnitt:
  - die Routing-Testbench unter `/config/routing` zeigt jetzt zusaetzlich eine `LLM router dry-run`-Entscheidung
  - die LLM-Schicht sieht nur den begrenzten Kandidatenraum aus deterministischem Treffer plus akzeptierten Qdrant-Kandidaten
  - Ausgabe bleibt bewusst rein beobachtend/adminseitig; noch keine Live-Ausfuehrung im Chat-Routing
- Routing-/Admin-Integration:
  - `/config/routing`
  - `/config/routing-index/test`
  - geben die LLM-Dry-run-Entscheidung jetzt mit aus
- Tests:
  - Routing-Admin, Config-Routing und Pipeline-Regressions fuer den neuen Dry-run-Schnitt gruen
- Release-Label:
  - `0.1.0-alpha122`

### alpha121

- enthaelt den kompletten Fixstand bis einschliesslich `alpha120`
- Routing-/SSH-Uptime-Fix:
  - natuerliche Fragen wie `Wie lange ist mein DNS Server schon online?` werden jetzt ebenfalls als SSH-`uptime` erkannt
  - dieselbe Formulierung stuetzt jetzt auch die Preferred-Kind-Inferenz fuer das Qdrant-Routing
  - dadurch faellt diese Phrase nicht mehr in generische LLM-/Memory-Antworten zurueck
- Tests:
  - gezielte Regressionen fuer Capability-Router, Pipeline und Routing-Resolver gruen
- intern verifiziert auf der echten internen ARIA:
  - GUI-Update-Button zog `aria-alpha121-local.tar` sauber vom NAS und aktualisierte erfolgreich
  - Config / Profile / Memory / Theme blieben nach dem Update erhalten
  - `Wie lange ist mein DNS Server schon online?` fuehrte korrekt `uptime` auf dem SSH-Profil `pihole1` aus
- Release-Label:
  - `0.1.0-alpha121`

### alpha120

- enthaelt den kompletten Fixstand bis einschliesslich `alpha119`
- Runtime-Reload-Hardening:
  - `_reload_runtime()` baut jetzt ein frisches Runtime-Bundle fuer `settings`, `prompt_loader`, `usage_meter`, `llm_client` und `pipeline`
  - der Swap auf die neue Runtime erfolgt atomar unter `threading.RLock`, statt die einzelnen Objekte nacheinander zu ueberschreiben
  - Startup-/Preflight-Diagnostics greifen konsistent auf den aktuellen Runtime-Stand zu
  - Stats-, Activities-, Skills-, Memories- und Config-Routen lesen Runtime-Objekte ueber Live-Getter statt eingefrorene Referenzen
- Config-/Session-Konsistenz:
  - `ConfigRouteDeps` nutzt fuer `auth_session_max_age_seconds` jetzt ebenfalls einen Getter
  - Session-Cookies bleiben damit nach Runtime-Reloads auf dem aktuellen Security-Stand
- Tests:
  - app-nahe Regressionen fuer Config-Routen, Chat-/Session-Pfade, Update-UI, Stats und den neuen Dynamic-Proxy gruen
  - voller Testlauf: `501 passed`
- Release-Label:
  - `0.1.0-alpha120`

### alpha119

- enthaelt den kompletten Fixstand bis einschliesslich `alpha118`
- Memory-Map / Routing-Graph:
  - Routing-Collections erscheinen jetzt nicht nur als Textblock, sondern auch sichtbar im Memory-Graph
  - Routing haengt als eigener System-Zweig in der Grafik und verlinkt auf `/config/routing`
- Routing / SSH-Intent:
  - natuerliche Fragen wie `Wie lange laeuft mein DNS Server schon?` werden jetzt ebenfalls als SSH-`uptime` erkannt
  - dieselbe Formulierung stuetzt jetzt auch die Preferred-Kind-Inferenz fuer Qdrant-Routing
  - dadurch faellt diese Frage nicht mehr in eine generische LLM-Antwort zurueck
- Tests:
  - gezielte Regressionen fuer Memory-Graph, Capability-Router, Pipeline und Routing-Resolver gruen
- intern verifiziert auf der echten internen ARIA:
  - GUI-Update-Button zog `aria-alpha119-local.tar` sauber vom NAS und aktualisierte erfolgreich
  - Config / Profile / Memory blieben nach dem Update erhalten
  - Routing-Collection im Memory-Graph sichtbar
  - `Wie lange laeuft mein DNS Server schon?` fuehrte korrekt `uptime` auf dem SSH-Profil aus
- Release-Label:
  - `0.1.0-alpha119`

### alpha118

- enthaelt den kompletten Fixstand bis einschliesslich `alpha117`
- Managed-Update-Hardening v2:
  - `aria-stack.sh validate` prueft jetzt nicht mehr nur `config.yaml`, sondern auch die Bind-Mounts und Sync-Sicht fuer `config`, `prompts` und `data`
  - `/app/config`, `/app/prompts` und `/app/data` werden explizit gegen die erwarteten Host-Pfade validiert
  - `prompts/persona.md` und die Auth-DB werden Host-vs-Container geprueft; fuer leere frische Setups gibt es einen `data`-Fallback-Check auf die Kernverzeichnisse
  - der Managed-Update-Helper hebt die echte Validate-Ursache jetzt in `last_error`/UI hoch, statt nur generisch `exit code 1` zu melden
- Admin-/Memory-Map:
  - Routing-Qdrant-Collections erscheinen jetzt separat in der Memory Map als System-/Routing-Collections
  - semantisches User-Memory und Routing-Index bleiben in der Anzeige sauber getrennt
- SSH-UX:
  - harmlose `known hosts`-Warnungen beim ersten SSH-Kontakt werden nicht mehr als sichtbarer `STDERR`-Fehler gezeigt
- Tests:
  - gezielte Tests fuer Setup-/Update-Helfer, Update-UI, Memory-Map und SSH-Output gruen
- Release-Label:
  - `0.1.0-alpha118`

### alpha117

- enthaelt den kompletten Fixstand bis einschliesslich `alpha116`
- Routing-/Intent-Fix:
  - natuerliche Laufzeit-/Uptime-/Healthcheck-Fragen werden jetzt als SSH-Command geplant
  - Beispiel: "Zeig mir die Laufzeit vom primaeren DNS Server" wird zu `ssh_command` mit `uptime`
  - SFTP-`file_read` greift nicht mehr nur wegen "zeig/zeige", wenn eigentlich ein Server-Status gefragt ist
  - der SSH-Intent kann mit explizitem Alias direkt routen oder ohne Alias ueber den Qdrant-Routing-Index aufgeloest werden
- Tests:
  - Capability-Router-Regression fuer Laufzeitfragen via Alias
  - Capability-Router-Regression fuer Laufzeitfragen ohne Ziel, damit Qdrant anschliessend aufloesen kann
  - Pipeline-Regression mit SSH und SFTP parallel, damit Laufzeitfragen vor SFTP als SSH ausgefuehrt werden
- Release-Label:
  - `0.1.0-alpha117`

### alpha116

- enthaelt den kompletten Fixstand bis einschliesslich `alpha115`
- Routing-UI:
  - `/config/routing` hat jetzt einen direkten Schalter fuer Live-Qdrant-Routing im Chat
  - Threshold und Kandidatenlimit koennen direkt auf der Routing-Seite angepasst werden
  - Option "bei unsicherem Qdrant-Routing nachfragen statt ausweichen" ist direkt konfigurierbar
  - Speichern erfolgt ueber einen eigenen Endpoint, getrennt vom Editor fuer Memory-/Routing-Regeln
- Tests:
  - UI zeigt den neuen Live-Routing-Save-Block
  - Speichern persistiert Enable/Disable, Threshold, Limit und Ask-on-low-confidence sauber in `config.yaml`
- Release-Label:
  - `0.1.0-alpha116`

### alpha115

- enthaelt den kompletten Fixstand bis einschliesslich `alpha114`
- Qdrant-Routing-Testbench / Live-Routing:
  - Auto-Modus erkennt aus dem Prompt nun den bevorzugten Connection-Typ
  - Laufzeit, uptime, Healthcheck, Befehl, Kommando und aehnliche Aktionen werden als SSH-Intent gewertet
  - Datei, Pfad, Ordner, Verzeichnis, Upload/Download werden als SFTP-Intent gewertet
  - Discord-Nachrichten und RSS-/News-Fragen bekommen ebenfalls eigene Typ-Hints
  - bei erkanntem Typ werden Qdrant-Kandidaten anderer Connection-Typen verworfen statt als finale Route akzeptiert
  - Qdrant fragt bei gesetztem/erkanntem Typ mehr Kandidaten ab und filtert danach hart, damit ein semantisch passender SSH-Treffer nicht von SFTP-Kandidaten verdeckt wird
  - die Testbench zeigt erkannte Auto-Typen und verworfene Kandidaten nachvollziehbar an
- Tests:
  - Regression fuer deutsche DNS-/Laufzeit-Fragen, bei denen SFTP hoeher scort als SSH
  - Regression fuer Auto-Intent-Erkennung in Resolver und Routing-Testbench
- Release-Label:
  - `0.1.0-alpha115`

### alpha114

- enthaelt den kompletten Fixstand bis einschliesslich `alpha113`
- Qdrant-Routing-Index:
  - Connection-Profile werden als eigene Routing-Dokumente fuer SSH, SFTP, RSS, Discord und HTTP-API aufgebaut
  - Routing-Dokumente enthalten Titel, Beschreibung, Aliase, Tags und nicht-sensitive Verbindungsmetadaten
  - Secrets, Tokens, Webhooks und Passwoerter werden nicht in Routing-Texte geschrieben
- Admin-/Debug-Funktionen:
  - `/config/routing` zeigt Status, Collection, Dokumentanzahl, Fingerprint und Stale-Erkennung des Routing-Index
  - manueller Rebuild fuer den Routing-Index
  - Testbench fuer Routing-Fragen mit optional bevorzugtem Connection-Typ
  - `/stats` zeigt den Routing-Index-Zustand kompakt mit an
- Live-Routing:
  - Qdrant-Routing ist als Feature-Flag vorbereitet und standardmaessig aus
  - exakte Profilnamen, Aliase, Memory-Hints und deterministische Router gewinnen weiter vor Qdrant
  - bei veraltetem oder fehlendem Index fragt ARIA im Live-Modus nach statt unsicher auf falsche Tools zu fallen
- Tests:
  - neue Unit-/Integrationstests fuer Index-Building, Resolver, Admin-Status/Testbench und Pipeline-Fallbacks
- Release-Label:
  - `0.1.0-alpha114`

### alpha113

- enthaelt den kompletten Fixstand bis einschliesslich `alpha112`
- SFTP-Connections:
  - neues Feld `Service URL`
  - Metadaten-Hilfe ueber Web-Seite + LLM fuer Beschreibung, Aliase und Tags
  - `service_url` wird jetzt im Datenmodell, in der UI und beim Speichern sauber mitgefuehrt
- SSH-/Skill-Safety:
  - `{query}` und `{query:q}` in SSH-Custom-Command-Templates werden shell-gequotet gerendert
  - Backtick-/Newline-Blockade bleibt als zusaetzliche Sicherheitsgrenze aktiv
- Guardrails:
  - einfache Begriffe matchen token-/boundary-bewusst
  - Pfad-Guardrails behalten Prefix-/Substring-Matching fuer Unterpfade
- Skill-Runtime:
  - konstante Regexes vor-kompiliert
  - dynamische Condition-Regexes ueber kleinen LRU-Cache
- Release-Label:
  - `0.1.0-alpha113`

### alpha112

- enthaelt den kompletten Fixstand bis einschliesslich `alpha111`
- SSH- und RSS-Metadaten-Helfer respektieren jetzt die aktive ARIA-Sprache
  - bei `DE` werden Titel, Beschreibung, Aliase und Tags gezielt auf deutsche Routing-/Trigger-Begriffe ausgerichtet
  - bei `EN` entsprechend auf englische Begriffe
- Release-Label:
  - `0.1.0-alpha112`

### alpha111

- enthaelt den kompletten Fixstand bis einschliesslich `alpha110`
  - Managed-Update-Haertung
  - `aria-stack.sh repair`
  - Host-vs-Container-Config-Validierung nach Managed-Updates
- SSH-Connections:
  - neues Feld `Service URL`
  - Metadaten-Hilfe ueber Web-Seite + LLM fuer Beschreibung, Aliase und Tags
  - optionale Checkbox, beim Anlegen direkt ein passendes SFTP-Profil mitzuerzeugen
- Connection-UX:
  - `Create` auf den Connection-Seiten deutlich prominenter
- Release-Label:
  - `0.1.0-alpha111`

### alpha8

- Skill-Loeschen auf `/skills`
- Skill-Loeschen direkt im Wizard
- neue sauber benannte Background-Assets
- `Nodes Field` als zusaetzlicher Background
- Theme-/Background-Einbindung aktualisiert

### alpha9

- Logo-Fix im Build
- Skill-Wizard:
  - `Schritt duplizieren`
  - `Step ID` aus der sichtbaren UI entfernt
  - `SSH Command` als groesseres Feld mit hoeherem Limit
- neue Samples/Connections fuer:
  - `SMB`
  - `Discord`
  - `RSS`
- aktualisiertes Linux-Update-Sample

### alpha10

- Stats-Fix fuer `bepreiste Anfragen`
- `0.0`-Kosten zaehlen nicht mehr als bepreist
- fruehe Pipeline-Pfade loggen keine Fake-Preise mehr
- Release-Label:
  - `0.1.0-alpha10`

### alpha11

- Connection-UX auf den Connection-Seiten beruhigt:
  - bestehende Profile direkt anklickbar
  - `Bearbeiten` aus dem Kopfbereich entfernt
  - `Neu` als klarer Einstieg
  - im Create-Modus: `Zurueck zu Verbindungen`
- Skill-Wizard:
  - duplizierte Steps landen direkt unter dem aktuellen Step
  - Steps lassen sich nach oben/unten verschieben
  - Reihenfolge wird vor dem Speichern sauber neu nummeriert
- Custom-Skill-Prioritaet vor generischem Capability-Pfad
  - klar passende Skills gewinnen jetzt vor z. B. direktem Discord-Senden
- Release-Label:
  - `0.1.0-alpha11`

### alpha12

- Stats:
  - Qdrant-Groesse wird im separaten Docker-/Compose-Betrieb ueber Qdrant-Telemetrie/API ermittelt
  - `Startup Preflight` zeigt die vier Kernchecks auf Desktop als eine Reihe
- Release-Label:
  - `0.1.0-alpha12`

### alpha13

- Memory:
  - Chat-Forget raeumt leere Qdrant-Collections sofort auf
- Discord:
  - Skill-Error-Alerts werden gekuerzt/sanitized
  - Statuschips fuer `Testposts aktivieren` / `Skill-Ziel erlauben` sind klarer als Read-only-Anzeige gestaltet
- Connections:
  - SFTP `SSH-Daten uebernehmen` im Create-Modus speichert wieder korrekt ein neues Profil
  - RSS nutzt dieselbe `Neu` / Klick-auf-Karte-zum-Editieren-Logik wie die anderen Connection-Seiten
- UI:
  - Back-Pfeil sitzt sauber unter der Topbar und ist etwas sichtbarer
- Release-Label:
  - `0.1.0-alpha13`

### alpha14

- Stats / Statistics:
  - `Aktivitaeten & Runs` ist direkt in `/stats` integriert
  - der separate Menuepunkt `Aktivitaeten` ist aus dem User-Menue entfernt
  - Activity-KPIs stehen in einer kompakten 4er-Reihe mit Mobile-Fallback
- Pricing:
  - manueller Button `Preise aktualisieren` in `/stats`
  - OpenAI-/Anthropic-Preise werden aus `litellm.model_cost` in die lokale ARIA-Preisliste uebernommen
  - OpenRouter-Preise werden ueber `https://openrouter.ai/api/v1/models` synchronisiert
  - aktualisierte Preise werden in `config/config.yaml` persistiert
- Connections:
  - Karten aus `Live-Status aller Profile` sind jetzt der direkte Einstieg in den Edit-Modus
  - Zusatzbloecke wie `Geladenes Profil` / separate Direkt-Links sind entfernt
  - `ARIA_PUBLIC_URL` / `aria.public_url` wird fuer Host-/Discord-Links genutzt statt Docker-Bridge-IP
  - RSS-Save-Redirect auf `Zurueck zu Verbindungen` korrigiert
- RSS / OPML:
  - OPML Import/Export auf der RSS-Connection-Seite
  - OPML-Import erzeugt pro Feed ein eigenes RSS-Profil
  - doppelte Feed-URLs werden beim Import uebersprungen
  - pro RSS-Profil gibt es `poll_interval_minutes`
  - RSS-Seite nutzt bei frischem Status den Cache statt jeden Feed bei jedem Seitenaufruf live zu pingen
  - OPML-Export schreibt die RSS-Sammlung als OPML 2.0
- UI / i18n:
  - `Stats` heisst in DE jetzt `Statistiken`, in EN `Statistics`
- Release-Label:
  - `0.1.0-alpha14`

### alpha15

- Stats:
  - `Aktivitaeten & Runs` auf `/stats` unter `Live-Status aller konfigurierten Verbindungen` verschoben
- RSS:
  - OPML-Import-Upload repariert (`opml_file missing` / Multipart-CSRF)
  - `OPML Import / Export` als einklappbarer Block
  - RSS-Kategorien als einklappbare Gruppen
  - nach Klick auf einen Feed zeigt der Edit-Modus nur noch diesen Feed + Formular + Loeschen
- Release-Label:
  - `0.1.0-alpha15`

### alpha16

- LLM:
  - leere Provider-Antworten werden als sauberer `LLMClientError` behandelt
  - ARIA faellt dadurch nicht mehr still auf `Ich habe gerade keine Antwort erzeugt.` zurueck
- RSS:
  - `Jetzt pingen` fuer den aktuell gewaehlten Feed im Edit-Modus
  - `Kategorien mit LLM aktualisieren` ist jetzt ein klarer Button statt ein dezenter Link
  - EN-Label: `Refresh categories with LLM`
- Release-Label:
  - `0.1.0-alpha16`

### alpha17

- LLM:
  - Default `max_tokens` fuer neue Setups/Profile auf `4096` erhoeht
  - reduziert `finish_reason=length` bei normalen Chat-Antworten
- Pricing:
  - Kostenberechnung nutzt jetzt eine LiteLLM-Fallback-Preisliste
  - bekannte Modelle wie `gpt-5.1` bekommen dadurch auch dann USD-Kosten, wenn `pricing.chat_models` in der Config noch leer ist
- Release-Label:
  - `0.1.0-alpha17`

### alpha18

- Custom-Skill-Routing:
  - Description-Match entschaerft
  - generische Admin-/Storage-Fragen wie LVM/ZFS/Btrfs triggern den Linux-Updates-Skill nicht mehr nur wegen `Ubuntu` + `Server`
  - echte Linux-Update-Fragen triggern den Skill weiter
- RSS:
  - RSS-Verbindungstests nutzen jetzt einen browserartigen `User-Agent`
  - RSS-Skill-Reads nutzen denselben robusteren Header
  - behebt Feeds, die im Browser funktionieren, aber vorher in ARIA mit `HTTP Error 403: Forbidden` gescheitert sind
- Release-Label:
  - `0.1.0-alpha18`

### alpha19

- Mobile/iPhone:
  - `Admin aktiv` sitzt auf kleinen Screens rechts in der Menu-Zeile statt neben dem A.R.I.A.-Titel
  - Desktop bleibt unveraendert
- RSS:
  - RSS-Statuskarten auf der RSS-Seite nutzen beim Seitenaufbau nur noch den letzten Cache-Stand
  - bei fehlendem/abgelaufenem Cache wird **kein synchroner Live-Ping** mehr gestartet
  - stattdessen zeigt ARIA einen Hinweis und `Jetzt pingen` bleibt die explizite Live-Aktion pro Feed
  - Feed-Loeschen/Editieren blockiert dadurch nicht mehr 20-40 Sekunden wegen eines langsamen RSS-Endpunkts
  - RSS-Verbindungstests lesen mehr als den alten 8-KB-Ausschnitt und akzeptieren auch RSS-1.0-Roots wie `<rdf:RDF>`
  - behebt valide Feeds wie NVD/Debian, die vorher faelschlich mit `ungueltiges XML` rot wurden
  - RSS-Profile haben jetzt `group_name` als manuell setzbare Gruppe/Kategorie
  - OPML-Import uebernimmt die erste OPML-Kategorie als Start-Gruppe
  - OPML-Export nutzt `group_name` als Outline-Gruppe
  - `Kategorien mit LLM aktualisieren` sortiert nur noch Feeds ohne manuell gesetzte Gruppe neu
- Release-Label:
  - `0.1.0-alpha19`

### alpha20

- RSS:
  - Feld `Gruppe / Kategorie` bietet jetzt Dropdown-Vorschlaege aus bestehenden Gruppen, bleibt aber frei editierbar fuer neue Kategorien
  - Feed-URL-Dedupe normalisiert URLs vor Vergleich/Speicherung
  - Varianten wie `/feed`, `/feed/`, Default-Port `:443`, Fragment-Hashes und Tracking-Parameter wie `utm_*`/`fbclid` werden zusammengefuehrt
  - JSON-URLs in RSS liefern jetzt eine klare Fehlermeldung mit Hinweis auf HTTP-API-Connections
  - auf RSS-Detailseiten geht `Zurueck zur RSS-Uebersicht` wieder direkt nach `/config/connections/rss`
  - lokale RSS-Suche nur ueber RSS-Titel, URL, Ref, Gruppe und Tags
  - passende RSS-Gruppen klappen bei aktiver Suche automatisch auf
  - RSS-Gruppen werden alphabetisch sortiert
  - RSS-Gruppenuebersicht nutzt ein dichteres responsives 2-3-Spalten-Grid mit Mobile-Fallback
- Release-Label:
  - `0.1.0-alpha20`

### alpha21

- RSS:
  - globales `Ping-Intervall` fuer alle RSS-Feeds statt pro Feed einzeln pflegen
  - alle bestehenden RSS-Profile werden beim Speichern des globalen Intervalls auf denselben Wert synchronisiert
  - RSS-Poll-Faelligkeit wird pro Feed stabil per Hash-Offset gestaffelt, damit nicht alle Feeds auf derselben Intervall-Kante faellig werden
  - lokale RSS-Suche blendet nicht passende Gruppen/Feeds wieder korrekt aus
  - das Suchfeld reagiert auch auf das kleine `x` zum Leeren
  - natuerlichere RSS-Fragen wie `was fuer news gibs auf heise` werden besser als RSS-Intent erkannt
  - RSS-Routing nutzt jetzt auch Titel, Kurzbeschreibung, Aliase und Tags der RSS-Profile
  - Button `Check mit LLM` im RSS-Metadatenblock fuellt Titel, Kurzbeschreibung, Aliase und Tags vor bzw. ergaenzt sie
- Statistiken:
  - `Startup Preflight` und `Systemzustand` zeigen Status jetzt nur noch als gruene/gelbe/rote Laempchen statt ausgeschriebener `OK/Warn/Error`-Labels
- Themes:
  - neue Themes `CyberPunk Pulse`, `8-Bit Arcade`, `Amber CRT` und `Deep Space`
- Release-Label:
  - `0.1.0-alpha21`

### alpha22

- Themes:
  - `CyberPunk Pulse` staerker Richtung Hot-Pink/Magenta gezogen, weniger violette Flaechen
- Docs / Release:
  - Doku-Struktur unter `docs/` und `project.docu/history/` aufgeraeumt
  - `Hilfe` und `Produkt-Info` als Read-only-Seiten im UI angebunden
  - `LICENSE` und `THIRD_PARTY_NOTICES.md` ergaenzt
  - `docs/product/roadmap.md` als GitHub-tauglicher Roadmap-Snapshot ergaenzt
  - `docs/release/github-release-notes-template.md` als Release-Notes-Vorlage ergaenzt
  - `CHANGELOG.md` `Unreleased`-Block mit dem aktuellen dev-Stand befuellt
  - `README.md` und zentrale Public-Docs sprachlich/funktional auf den aktuellen Public-Alpha-Stand geglaettet
  - neutrale Beispielwerte in `docker/aria-stack.env.example`, `docs/setup/portainer-deploy-checklist.md` und `docs/help/memory.md`
  - `.gitignore` um Python-/Build-Artefakte und lokale TARs erweitert
- Onboarding:
  - Bootstrap-/Admin-/User-Modus in Login-, Benutzer- und Security-UI klarer erklaert
- Statistiken:
  - Statistik-Reset mit `RESET`-Bestaetigung auf `/stats`
  - Qdrant-Groessenanzeige robuster fuer separates Compose-/Portainer-Qdrant-Volume vorbereitet
- Memory:
  - Auto-Memory filtert fluechtige Einmalfragen und reine Tool-/Action-Prompts beim automatischen Persistieren staerker heraus
  - echte Fakten/Preferences und deklarativer Nutzerkontext werden weiter gespeichert
  - Architekturentscheidung festgehalten: Capability-Ergebnisse werden bewusst **nicht** pauschal automatisch in Memory persistiert; spaeter nur ueber gezielte Summary-/State-Memory-Flows
  - Memory-Export als JSON-Download in `/memories`
  - gewichtetes Multi-Collection-Recall mit einem expliziten Regression-Test gegen Fact-vs-Session-Ranking abgesichert
- Mobile/iPhone:
  - Chat-Debug-Header bricht lange `Tages-Kontext`- und `Login-Session`-IDs jetzt sauber um, statt horizontalen Page-Overflow zu erzeugen
- Release-Label:
  - `0.1.0-alpha22`

### alpha23

- Themes:
  - `CyberPunk Pulse` nochmals pinker gezogen, waehrend Helper-/Meta-/Status-Texte und Chips im Theme gezielt auf neon-gruen `#00ff00` gehen
- Mobile/iPhone:
  - Chat-Scroller und Message-Bubbles auf vertikales Panning geklemmt
  - horizontale Drift/seitliches Mitschieben beim Scrollen weiter reduziert
  - lange Bubble-Inhalte, Meta-Badges und Details-Zeilen brechen jetzt konsequent innerhalb der Bubble um
- Packaging:
  - `docs/` wird jetzt ins Docker-Image kopiert, damit `/help` und `/product-info` im Container nicht mehr auf fehlende Markdown-/SVG-Dateien laufen
- UI / Doku-Navigation:
  - `Produkt-Info` aus dem Top-Menue entfernt und stattdessen als Kachel unter `/help` verlinkt
- Statistiken:
  - Qdrant-Groessenanzeige faellt bei `Telemetry · n Collections`, aber `0 B`, jetzt erst noch auf lokale Storage-Pfade zurueck
  - `0 B` aus Qdrant-Telemetrie blockiert dadurch nicht mehr den Volume-/Filesystem-Fallback
- Release-Label:
  - `0.1.0-alpha23`

### alpha24

- UI / Produkt-Info:
  - `Copy Pack`-Kachel aus `/product-info` entfernt; dort bleiben nur Overview, Feature-Liste und Architektur
- Themes:
  - `CyberPunk Pulse`: Buttons und Menu-Beschriftung neon-gruen, damit die Controls klarer gegen die pinken Flaechen stehen
  - `Deep Space`: dunklerer, violett-/nebula-lastiger Farbschnitt, damit das Theme weniger nach `Harbor Blue` aussieht
- Samples / Skills / Connections:
  - `samples/` wird jetzt ins Docker-Image kopiert, damit Sample-Skills, Sample-Connections und Guardrail-Beispiele im Container unter `/app/samples` verfuegbar sind
  - `/skills` zeigt mitgelieferte Sample-Skills aus `/app/samples/skills` direkt an und kann sie serverseitig per Klick importieren
  - `/config` zeigt mitgelieferte Sample-Connections aus `/app/samples/connections` direkt an und kann sie serverseitig in `config.yaml` importieren, ohne bestehende Refs zu ueberschreiben
  - neuer Sample-Skill `rss-morning-briefing-to-discord-template.json` fuer ein taegliches, per LLM kuratiertes Multi-RSS-Briefing nach Discord
  - Skill-Wizard erklaert bei `llm_transform` jetzt direkt die Platzhalter `{prev_output}` und `{s1_output}` / `{s2_output}` fuer Multi-Step-Aggregation
- Release-Label:
  - `0.1.0-alpha24`

## Auf `dev` vorbereitet fuer den naechsten Build

- Hilfe:
  - `docs/help/alpha-help-system.de.md` und `docs/help/alpha-help-system.en.md` als praktische, menschenlesbare Alpha-Kurzhilfe in DE/EN ergaenzt
  - `/help` zeigt jetzt je nach aktiver UI-Sprache diese Alpha-Hilfe statt den internen Help-System-Entwurf `docs/help/help-system.md` direkt zu rendern
- Chat-Toolbox:
  - Skill-Eintraege zeigen jetzt den eigentlichen Skill-Namen als Titel, einen kleinen `/skill`-Badge und darunter Beschreibung/Beispiel-Trigger
  - lange Skill-Titel und Hinweise koennen in der Toolbox sauber umbrechen statt unsichtbar abgeschnitten zu werden
- Menue:
  - `Hilfe` sitzt jetzt nach `Einstellungen` und vor `Benutzer`
- README:
  - Root-`README.md` klar in `English`- und `Deutsch`-Abschnitt getrennt, mit EN zuerst und DE als eigener, eindeutig markierter Block weiter unten
- `/stats` -> `Systemzustand`: ARIA Runtime, Model Stack, Memory / Qdrant, Security Store und Activities / Logs bekommen jetzt ebenfalls die normalen Status-Laempchen
- Repo-/Privacy-Sweep:
  - persoenliche Dev-Host-Defaults aus `docker/pull-from-dev.sh` entfernt
  - `config/secrets.env` neutralisiert
  - Root-Artefakte `=1.2` und `=2.1` entfernt
  - `docs/setup/portainer-deploy-checklist.md` von `/home/fischerman/ARIA` auf neutraleren Beispielpfad umgestellt

### alpha154

- Routing / Personal Integrations:
  - erster echter `Google Calendar`-Produktpfad als `read-only`-Faehigkeit integriert
  - natuerliche Kalender-Prompts wie `was steht heute an?`, `was habe ich morgen im kalender?` und `wann ist mein naechster termin?` laufen jetzt ueber denselben Routing-/Planner-/Payload-/Guardrail-Pfad wie die restlichen Aktionen
  - neuer Executor `calendar_read` mit Google-Token-Refresh und read-only Event-Abfrage
- Connections / Produktfluss:
  - `Google Calendar` als eigener Connection-Typ mit Secure-Store fuer `client_secret` und `refresh_token`
  - read-only Connection-Test gegen Google-Kalender-Metadaten
- Memory / UX:
  - redundanten `Naechste Schritte`-Block auf `/memories` entfernt
  - `Auto-Memory`-Kachel auf `/memories` fuehrt jetzt direkt zum passenden Setup-Block
  - `Memory backend enabled` als irrefuehrenden Kill-Switch aus `/memories/config` entfernt; Qdrant-Setup haelt Memory jetzt aktiv
  - Restart-Flaeche fuer `Qdrant` und `SearXNG` unter `/config/operations`
- Robustheit:
  - externe Connection-Fehler fuer Auth, Berechtigungen, TLS/SSL, Timeout und Erreichbarkeit produktfaehiger formuliert
  - Connection-Koepfe sprechen klarer ueber `verbunden`, `Anmeldung fehlt` und `optional`
- Tests:
  - voller Testlauf: `602 passed, 11 warnings`
- Build-Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha154-local.tar`
- Release-Label:
  - `0.1.0-alpha154`

### alpha155

- Google Calendar / Produktfluss:
  - Setup-Seite fuer `Google Calendar` bewusst auf denselben Clean-/Domain-Stil getrimmt; die innere Hilfeflaeche ist keine weitere schwere `config-card` mehr
  - Google-Setup jetzt als echter Enduser-Flow direkt auf der Seite:
    - API aktivieren
    - OAuth Branding / Audience / Client vorbereiten
    - Refresh-Token im OAuth Playground erzeugen
    - Werte in ARIA eintragen
  - alle benoetigten Google-Links sind direkt auf der Seite sichtbar, damit die Konfiguration ohne externe Nebensuche machbar bleibt
  - Feldreihenfolge und Feldhinweise fuer `Client ID`, `Calendar ID`, `Timeout`, `Client Secret` und `Refresh Token` logisch nach dem realen Setup-Ablauf geordnet
- Tests:
  - voller Testlauf: `602 passed, 11 warnings`
- Build-Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha155-local.tar`
- Release-Label:
  - `0.1.0-alpha155`

## Noch offen / weiter sammeln

- Docker-Hub-Hinweis auf neue Version statt In-App-Update
- Memory-Export auf `prod` live gegen echte Qdrant-Daten testen
- weitere Single-User-/Personalisierungs-Polishes

### Public release 0.1.0-alpha.122

- Oeffentliche Versionslinie von `0.1.0-alpha121` auf `0.1.0-alpha122` angehoben.
- Roll-up Release ueber die intern getesteten Staende `alpha122` bis `alpha167`.
- Git:
  - Commit: `bae8a94`
  - Tag: `v0.1.0-alpha.122`
- Docker Hub:
  - `fischermanch/aria:0.1.0-alpha.122`
  - `fischermanch/aria:alpha`
  - Digest: `sha256:f023bf58cd0d3e32007bb769ea0288beb4390644ea4662adf73cee99d77a35ae`
- Release-Schwerpunkte:
  - `Google Calendar` read-only als erster persoenlicher Enduser-Pfad
  - `Notizen` als eigener Markdown-first Bereich mit Qdrant-Indexierung
  - `Beobachtete Webseiten` als neue Quellen-Verbindung
  - vereinheitlichter Routing-/Planner-/Guardrail-Pfad
  - groesserer UI-, Doku- und Runtime-Cleanup
- Tests:
  - voller Testlauf: `634 passed, 11 warnings`
- Hinweis:
  - GitHub Release API-Eintrag konnte in dieser Shell nicht erzeugt werden, weil `GITHUB_TOKEN` hier nicht gesetzt ist.

### Public release 0.1.0-alpha.125

- Oeffentliche Versionslinie von `0.1.0-alpha124` auf `0.1.0-alpha125` angehoben.
- Fokus bewusst eng auf den Managed-Update-Pfad gelegt.
- Git:
  - Tag: `v0.1.0-alpha.125`
- Docker Hub:
  - `fischermanch/aria:0.1.0-alpha.125`
  - `fischermanch/aria:alpha`
- Release-Schwerpunkte:
  - fehlgeschlagene Managed-Updates fuehren nach einem kaputten `validate` jetzt automatisch genau einen `repair` aus
  - stale roter `/updates`-Status heilt sich automatisch, sobald `./aria-stack.sh validate` wieder sauber ist
  - `repair` / `restart` / `update` behandeln jetzt die komplette Runtime-Gruppe inklusive `qdrant`, `searxng-valkey` und `searxng`
