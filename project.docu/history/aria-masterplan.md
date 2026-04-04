# ARIA — Masterplan

## Adaptive Reasoning & Intelligence Agent

**Version:** 3.0 — 22. Februar 2026
**Autor:** Fischerman + Claude
**Vorgänger:** Jarvis v1 (FastAPI), Jarvis v2 (n8n) — beide verworfen
**Sprache:** Python 3.12+
**Lizenz:** MIT (geplant, Open Source)

---

## 1. Vision

> **Ein Container. Eine Config. Läuft.**

ARIA ist ein modularer, token-sparsamer AI-Agent der lokal läuft, keine Cloud-Abhängigkeiten hat und über Prompt-Files personalisierbar ist. Jeder kann ARIA installieren, seine eigene LLM-Anbindung konfigurieren und sofort einen intelligenten Assistenten haben.

**Kernversprechen:**
- Null laufende Kosten (lokale LLMs)
- Volle Kontrolle über jeden Token
- Skills erweiterbar ohne Code zu ändern
- Container-ready für Distribution

---

## 2. Lessons Learned

Was wir aus den gescheiterten Versuchen gelernt haben:

| Versuch | Problem | Lektion für ARIA |
|---|---|---|
| nanobot + qwen2.5:7b | "No API key" Fehler trotz korrekter Config | Kein Framework nutzen das wir nicht kontrollieren |
| OpenClaw + qwen3:8b | 1M Tokens in 12h ohne Nutzen, Heartbeat-Spam | Token-Budget ist Pflicht, kein Bootstrap-Overhead |
| OpenRouter | Unerwartete Kosten | Lokale LLMs first, Cloud nur bewusst |
| Jarvis v2 (n8n) | Workflows nicht mit Codex/Roo baubar | Python statt n8n = AI-Tools können mithelfen |
| Mem0 | JSON-Parsing-Fehler, undurchsichtiges Verhalten | Qdrant direkt ansprechen, keine Blackbox |

## 2.1 Strategie-Update Websuche (24. Maerz 2026)

- Websuche bleibt eine Kernfunktion von ARIA.
- Standard-Architektur: provider-native Web-Tooling (über LLM/Gateway), um den Default-Stack schlank zu halten.
- SearXNG bleibt möglich, aber nur als optionale Erweiterung für Power-User.
- Folge: Im Default-Deployment ist kein separater SearXNG-Container erforderlich.

---

## 3. Designprinzipien

### 3.1 Token-Sparsamkeit

Jeder Request an das LLM wird budgetiert:

```
┌─────────────────────────────────────────────┐
│              TOKEN-BUDGET                    │
│                                             │
│  System-Prompt:    ~200 Tokens (fix)        │
│  Persona (Prompt-File): ~100 Tokens (fix)   │
│  Skill-Kontext:   ~50 Tokens (pro Skill)    │
│  Memory-Kontext:  ~200 Tokens (Top-3)       │
│  Tool-Resultate:  ~300 Tokens (gekürzt)     │
│  User-Nachricht:  variabel                  │
│  ─────────────────────────────────          │
│  TOTAL pro Request: ~900-1200 Tokens        │
│                                             │
│  Vergleich OpenClaw: ~8000-15000 Tokens     │
└─────────────────────────────────────────────┘
```

**Wie wir das erreichen:**
- Kein Bootstrap-File laden bei jedem Request
- System-Prompt ist minimal und fest
- Persona kommt aus einem kurzen Prompt-File (~10 Zeilen)
- Tool-Resultate werden vor dem LLM-Call gekürzt (Top-N, max chars)
- Memory-Kontext ist auf Top-3 Treffer begrenzt
- Kein Heartbeat, kein Polling, kein Agent-Loop

### 3.2 Prompt-Files statt Code

```
aria/prompts/
├── persona.md          # Wer bin ich? Name, Ton, Sprache
├── skills/
│   ├── web_search.md   # Wann und wie suche ich im Web?
│   ├── memory.md       # Wie gehe ich mit Erinnerungen um?
│   ├── documents.md    # Wie fasse ich Dateien zusammen?
│   └── home.md         # Wie steuere ich Smart Home?
└── examples/
    ├── persona_butler.md
    ├── persona_coder.md
    └── persona_minimal.md
```

**Inhalt einer persona.md:**

```markdown
# Persona

Name: Reginald
Sprache: Schweizerisches Hochdeutsch (ä ö ü, ss statt ss)
Ton: Direkt, kompetent, ohne Floskeln
Unsicherheiten: Klar kennzeichnen
Längenlimit: Maximal 3 Absätze, ausser User fragt explizit nach mehr
```

**Inhalt einer skills/web_search.md:**

```markdown
# Skill: Websuche

Trigger: User fragt nach aktuellen Informationen, News, Fakten
Verhalten: Fasse die Top-5-Resultate zusammen, nenne Quellen
Format: Kurz und faktisch, keine Floskeln
Sprache: In der Sprache des Users antworten
```

Der User ändert diese Files, nicht den Python-Code. Ein neuer Skill = ein neues Markdown-File + ein Python-Modul.

### 3.3 Container-First

```
┌─────────────────────────────────────────────┐
│  Docker Container: aria                      │
│                                              │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ FastAPI      │  │ /prompts/ (Volume)   │  │
│  │ Port 8800    │  │ /config/ (Volume)    │  │
│  └──────┬──────┘  └──────────────────────┘  │
│         │                                    │
│         │ Outbound HTTP only                 │
│         ├──→ LLM (Ollama / LiteLLM / API)   │
│         ├──→ Qdrant                          │
│         ├──→ SearXNG                         │
│         └──→ Home Assistant                  │
│                                              │
│  Kein eingebetteter LLM, kein Qdrant,        │
│  keine Datenbank. Nur der Agent.             │
└─────────────────────────────────────────────┘
```

**Warum nur der Agent?**
- User bringt sein eigenes LLM mit (Ollama, LiteLLM, OpenRouter, whatever)
- User bringt sein eigenes Qdrant mit (oder ARIA erstellt beim Start eine SQLite-Fallback-Memory)
- Weniger Abhängigkeiten = weniger Fehlerquellen = einfachere Distribution

---

## 4. Architektur

### 4.0 Naechster Architekturblock: Capability Routing + Memory Assist

Der naechste Ausbaupfad ist bewusst **capability-basiert** und nicht nur keyword-/connection-getrieben.

Zielbild:

- User beschreibt fachlich, was er will
- ARIA erkennt die Capability
- Memory hilft bei Connection-/Ziel-Aufloesung
- ein deterministischer Executor fuehrt die Aktion aus

Startpunkt:

- `file_read`
- `file_write`
- `file_list`
- zuerst ueber `SFTP`, spaeter auch `SMB`

Wichtig:

- LLM darf die Absicht strukturieren
- die Ausfuehrung bleibt kontrolliert und validiert
- Memory wird von Anfang an als Assistenzschicht einbezogen
- die Struktur soll spaeter user-generierte Erweiterungen via UI vorbereiten

Detailplan:

- `project.docu/capability-routing-plan.md`

```
┌──────────────────────────────────────────────────────────────┐
│                        ARIA CORE                              │
│                                                               │
│  ┌──────────────┐                                             │
│  │  Web UI       │ ← Schlankes eigenes Frontend               │
│  │  (FastAPI +   │                                            │
│  │   Jinja2/     │                                            │
│  │   HTMX)       │                                            │
│  └──────┬───────┘                                             │
│         │                                                     │
│  ┌──────▼───────┐                                             │
│  │  Channel      │ ← Adapter-Pattern für verschiedene Inputs  │
│  │  Adapter      │    Web UI, Discord, REST API, Telegram     │
│  │  Layer        │    Jeder Adapter ist ein dünner Client      │
│  └──────┬───────┘                                             │
│         │                                                     │
│  ┌──────▼───────────────────────────────────────────────┐     │
│  │                    PIPELINE                           │     │
│  │                                                       │     │
│  │  1. Prompt-File Loader                                │     │
│  │     └─ Lädt persona.md + relevante skills/*.md        │     │
│  │                                                       │     │
│  │  2. Router (Stufenmodell)                             │     │
│  │     └─ Stufe 1: Keyword-Match (0 Tokens, instant)    │     │
│  │     └─ Stufe 2: Embedding-Similarity (0 LLM-Tokens)  │     │
│  │     └─ Stufe 3: LLM-Klassifikation (Fallback)        │     │
│  │                                                       │     │
│  │  3. Skill Executor                                    │     │
│  │     └─ Ruft aktive Skills auf (parallel wenn möglich) │     │
│  │                                                       │     │
│  │  4. Context Assembler                                 │     │
│  │     └─ Baut den finalen Prompt mit Token-Budget       │     │
│  │                                                       │     │
│  │  5. LLM Client                                        │     │
│  │     └─ Sendet an LiteLLM/Ollama, empfängt Antwort    │     │
│  │                                                       │     │
│  │  6. Token Tracker                                     │     │
│  │     └─ Loggt Token-Verbrauch pro Request + Total      │     │
│  │                                                       │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐     │
│  │                    SKILLS                             │     │
│  │                                                       │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │     │
│  │  │ memory   │ │documents │ │web_search│ │  home   │ │     │
│  │  │ (Qdrant) │ │(Dateien) │ │(SearXNG) │ │  (HA)   │ │     │
│  │  └──────────┘ └──────────┘ └──────────┘ └─────────┘ │     │
│  │                                                       │     │
│  │  Jeder Skill: 1 Python-File + 1 Prompt-File          │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. Komponenten im Detail

### 5.1 Pipeline

Die Pipeline verarbeitet jede Nachricht in exakt 6 Schritten. Kein Agent-Loop, kein Branching, keine Rekursion.

```python
async def process(message: str, user_id: str, source: str) -> Response:
    # 1. Prompt-Files laden (gecached, nur bei Änderung neu)
    persona = prompt_loader.get_persona()
    
    # 2. Routen — stufenweise, so billig wie möglich
    intents = router.classify(message)  # Stufe 1-3
    
    # 3. Skills ausführen
    skill_results = await skill_executor.run(intents, message, user_id)
    
    # 4. Kontext zusammenbauen (mit Token-Budget)
    prompt = context_assembler.build(persona, skill_results, message)
    
    # 5. LLM aufrufen
    response = await llm_client.chat(prompt)
    
    # 6. Token-Verbrauch loggen
    token_tracker.log(response.usage, intents, source)
    
    return Response(text=response.content, intents=intents, tokens=response.usage)
```

### 5.2 Router — Stufenmodell

Der Router ist DAS Token-Spar-Feature. Statt bei jeder Nachricht das LLM zu fragen "was soll ich tun?", versucht er zuerst kostenlose Methoden:

```
Nachricht: "Schalte das Licht im Büro ein"

Stufe 1: Keyword-Match
  → "schalte" + "licht" → home_control ✓
  → FERTIG (0 Tokens, <1ms)

Nachricht: "Was denkst du über die aktuelle Lage?"

Stufe 1: Keyword-Match → kein Treffer
Stufe 2: Embedding-Similarity
  → Embedding der Nachricht vs. Skill-Embeddings
  → Nächster Skill: chat (Score 0.82) ✓
  → FERTIG (0 LLM-Tokens, ~50ms, nur Embedding)

Nachricht: "Erinnerst du dich was ich letzte Woche über Docker gesagt habe und such mal ob es da was Neues gibt?"

Stufe 1: Keyword-Match → "erinnerst" → memory_recall (partial)
Stufe 2: Embedding-Similarity → web_search auch relevant
Stufe 3: LLM-Klassifikation (Fallback für Multi-Intent)
  → {"intents": ["memory_recall", "web_search"]} ✓
  → Kostet ~150 Tokens, aber nur bei komplexen Fällen
```

**Statistik-Erwartung:**
- ~70% der Nachrichten: Stufe 1 (Keywords) → 0 Tokens
- ~20% der Nachrichten: Stufe 2 (Embeddings) → 0 LLM-Tokens
- ~10% der Nachrichten: Stufe 3 (LLM) → ~150 Tokens

### 5.3 Skills — Einheitliches Interface

```python
# aria/skills/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class SkillResult:
    skill_name: str
    content: str          # Text-Kontext fürs LLM
    success: bool
    tokens_saved: int = 0  # Wieviel wurde gekürzt

class BaseSkill(ABC):
    name: str
    description: str
    keywords: list[str]           # Für Router Stufe 1
    prompt_file: str              # Pfad zur Skill-Prompt-Datei
    max_context_chars: int = 1500 # Token-Budget pro Skill

    @abstractmethod
    async def execute(self, query: str, params: dict) -> SkillResult:
        """Führt den Skill aus und gibt Text-Kontext zurück."""
        ...
    
    def truncate(self, text: str) -> str:
        """Kürzt Output auf max_context_chars."""
        if len(text) <= self.max_context_chars:
            return text
        return text[:self.max_context_chars] + "\n[... gekürzt]"
```

#### Skill: Memory (Qdrant direkt)

```python
# aria/skills/memory.py
class MemorySkill(BaseSkill):
    name = "memory"
    keywords = ["erinnerst", "merk dir", "vergiss nicht", "letztes mal",
                "weisst du noch", "gespeichert", "speichere"]
    prompt_file = "skills/memory.md"
    
    async def store(self, text: str, user_id: str, metadata: dict):
        """Erzeugt Embedding und speichert in Qdrant."""
        embedding = await self.embed(text)
        await self.qdrant.upsert(
            collection="aria_memory",
            points=[{
                "id": uuid4(),
                "vector": embedding,
                "payload": {
                    "text": text,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    **metadata
                }
            }]
        )
    
    async def recall(self, query: str, user_id: str, top_k: int = 3):
        """Sucht ähnliche Erinnerungen."""
        embedding = await self.embed(query)
        results = await self.qdrant.search(
            collection="aria_memory",
            query_vector=embedding,
            query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
            limit=top_k
        )
        return self.truncate(
            "\n".join(f"- {r.payload['text']}" for r in results)
        )
```

#### Skill: Documents

```python
# aria/skills/documents.py
class DocumentSkill(BaseSkill):
    name = "documents"
    keywords = ["datei", "dokument", "pdf", "lies", "zusammenfassung",
                "inhalt", "text aus"]
    prompt_file = "skills/documents.md"
    
    async def execute(self, query: str, params: dict) -> SkillResult:
        """Liest Dateien und gibt Inhalt als Kontext zurück."""
        file_path = params.get("file_path")
        if not file_path:
            return SkillResult(self.name, "Keine Datei angegeben.", False)
        
        content = await self.read_file(file_path)
        summary = self.truncate(content)
        return SkillResult(self.name, summary, True)
```

#### Skill: Web Search (SearXNG)

```python
# aria/skills/web_search.py
class WebSearchSkill(BaseSkill):
    name = "web_search"
    keywords = ["suche", "such", "google", "news", "aktuell",
                "was passiert", "neuigkeiten", "wetter"]
    prompt_file = "skills/web_search.md"
    
    async def execute(self, query: str, params: dict) -> SkillResult:
        search_query = params.get("search_query", query)
        results = await self.searxng.search(
            query=search_query,
            language="de-CH",
            max_results=5
        )
        formatted = "\n".join(
            f"[{i+1}] {r['title']}\n{r['content'][:200]}\nQuelle: {r['url']}"
            for i, r in enumerate(results)
        )
        return SkillResult(self.name, self.truncate(formatted), True)
```

#### Skill: Home Assistant (Phase 2)

```python
# aria/skills/home.py
class HomeSkill(BaseSkill):
    name = "home"
    keywords = ["licht", "lampe", "heizung", "temperatur", "schalte",
                "storen", "rollladen", "klima"]
    prompt_file = "skills/home.md"
    
    # Entity-Mapping aus config.yaml laden
    # Whitelist-only: Nur konfigurierte Entities sind steuerbar
```

### 5.4 Context Assembler

```python
# aria/core/context.py
class ContextAssembler:
    """Baut den finalen Prompt mit Token-Budget."""
    
    MAX_TOTAL_TOKENS = 2000  # Gesamtbudget für Input
    
    def build(self, persona: str, skill_results: list[SkillResult],
              user_message: str, memory_context: str = "") -> list[dict]:
        
        system = f"{persona}\n\n"
        
        # Skill-Kontext hinzufügen (gekürzt)
        context_parts = []
        for result in skill_results:
            if result.success and result.content:
                context_parts.append(f"--- {result.skill_name} ---\n{result.content}")
        
        if memory_context:
            context_parts.append(f"--- erinnerung ---\n{memory_context}")
        
        context = "\n\n".join(context_parts)
        
        if context:
            user_content = (
                f"Kontext:\n{context}\n\n"
                f"Frage: {user_message}"
            )
        else:
            user_content = user_message
        
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content}
        ]
```

### 5.5 Token Tracker

```python
# aria/core/token_tracker.py
class TokenTracker:
    """Loggt Token-Verbrauch. Kein Ratelimiting, nur Transparenz."""
    
    async def log(self, usage: dict, intents: list, source: str):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "intents": intents,
            "source": source,
            "router_level": self.last_router_level  # 1, 2, oder 3
        }
        # Append to JSON-Lines Logfile
        async with aiofiles.open(self.log_path, "a") as f:
            await f.write(json.dumps(entry) + "\n")
    
    async def get_stats(self, days: int = 7) -> dict:
        """Token-Statistik für Dashboard."""
        return {
            "total_tokens_7d": ...,
            "avg_tokens_per_request": ...,
            "requests_by_router_level": ...,
            "requests_by_intent": ...,
        }
```

### 5.6 LLM Client

```python
# aria/core/llm_client.py
from litellm import acompletion

class LLMClient:
    """Wrapper um LiteLLM SDK. Ein Import, alle Modelle."""
    
    def __init__(self, config: dict):
        self.model = config["model"]          # z.B. "ollama_chat/qwen3:8b"
        self.api_base = config.get("api_base") # z.B. "http://172.31.100.15:11434"
        self.temperature = config.get("temperature", 0.4)
        self.max_tokens = config.get("max_tokens", 1024)
    
    async def chat(self, messages: list[dict]) -> dict:
        response = await acompletion(
            model=self.model,
            messages=messages,
            api_base=self.api_base,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response
    
    async def classify(self, messages: list[dict]) -> dict:
        """Spezialfall: Niedrige Temperatur, wenig Tokens."""
        response = await acompletion(
            model=self.model,
            messages=messages,
            api_base=self.api_base,
            temperature=0.1,
            max_tokens=200,
        )
        return response
```

### 5.7 Channel Adapters

```python
# aria/channels/base.py
class BaseChannel(ABC):
    """Adapter-Interface für verschiedene Frontends."""
    
    @abstractmethod
    async def start(self):
        """Startet den Channel (Webhook, Bot, etc.)."""
        ...
    
    @abstractmethod
    async def send(self, user_id: str, message: str):
        """Sendet eine Nachricht an den User."""
        ...
```

```python
# aria/channels/web.py — Eingebautes Web-UI
class WebChannel(BaseChannel):
    """Schlankes Web-UI mit HTMX für Live-Updates."""
    # FastAPI + Jinja2 Templates + HTMX
    # Kein React, kein Node.js, kein Build-Step
    # Ein paar HTML-Templates, fertig
```

```python
# aria/channels/discord.py — Discord Bot
class DiscordChannel(BaseChannel):
    """Dünner Discord-Client, alle Logik in ARIA Core."""
    # discord.py, ~50 Zeilen Code
```

```python
# aria/channels/api.py — REST API
class APIChannel(BaseChannel):
    """OpenAI-kompatibler /v1/chat/completions Endpoint."""
    # Damit kann jedes Frontend das OpenAI-API spricht
    # sich an ARIA anbinden (z.B. OpenWebUI)
```

---

## 6. Web UI

Schlank, schnell, keine Abhängigkeiten. Kein React, kein npm, kein Build-Schritt.

**Stack:** FastAPI + Jinja2 + HTMX + ~200 Zeilen CSS

```
┌─────────────────────────────────────────────┐
│  ARIA                              [⚙ Stats]│
├─────────────────────────────────────────────┤
│                                             │
│  Du: Wie wird das Wetter morgen?            │
│                                             │
│  ARIA: Morgen wird es in Zürich rund 8°C    │
│  bei bewölktem Himmel.                      │
│  [🔍 web_search · 847 tokens]              │
│                                             │
│  Du: Merk dir dass ich morgen frei habe     │
│                                             │
│  ARIA: Gespeichert.                         │
│  [💾 memory · 312 tokens]                  │
│                                             │
├─────────────────────────────────────────────┤
│  [Nachricht eingeben...]          [Senden]  │
└─────────────────────────────────────────────┘
```

**Features:**
- Token-Verbrauch pro Nachricht sichtbar
- Welcher Skill/Intent aktiv war
- Stats-Seite: Token-Verbrauch über Zeit, häufigste Intents
- Mobile-friendly (responsive)
- Dark Mode

---

## 7. Konfiguration

### config.yaml

```yaml
aria:
  host: "0.0.0.0"
  port: 8800
  log_level: "info"

llm:
  model: "ollama_chat/qwen3:8b"
  api_base: "http://localhost:11434"   # Ollama direkt
  # api_base: "http://172.31.10.210:4000" # Oder via LiteLLM
  temperature: 0.4
  max_tokens: 1024
  # Optional: Separates Modell für Klassifikation
  # classifier_model: "ollama_chat/qwen3:8b"

embeddings:
  model: "nomic-embed-text"
  api_base: "http://localhost:11434"   # Ollama

memory:
  enabled: true
  backend: "qdrant"                    # oder "sqlite" als Fallback
  qdrant_url: "http://localhost:6333"
  collection: "aria_memory"
  top_k: 3                            # Max Erinnerungen pro Request

skills:
  web_search:
    enabled: true
    searxng_url: "http://localhost:8080"
    max_results: 5
    language: "de-CH"
    timeout: 10
  
  documents:
    enabled: true
    allowed_paths:                     # Sicherheit: Nur diese Pfade
      - "/data/documents"
    max_file_size_mb: 10
  
  home:
    enabled: false                     # Phase 2
    ha_url: "http://localhost:8123"
    ha_token: ""
    entities: {}                       # Whitelist

channels:
  web:
    enabled: true                      # Immer an
  discord:
    enabled: false
    token: ""
    allowed_users: []
  api:
    enabled: true                      # OpenAI-kompatibler Endpoint
    auth_token: ""                     # Optional: Bearer Token

prompts:
  persona: "prompts/persona.md"
  skills_dir: "prompts/skills/"

token_tracking:
  enabled: true
  log_file: "/data/logs/tokens.jsonl"
```

### Environment Variables (Override)

```bash
ARIA_LLM_MODEL=ollama_chat/qwen3:8b
ARIA_LLM_API_BASE=http://172.31.100.15:11434
ARIA_QDRANT_URL=http://172.31.10.210:6333
ARIA_SEARXNG_URL=http://172.31.10.210:8080
ARIA_DISCORD_TOKEN=xxx
ARIA_HA_TOKEN=xxx
```

Env-Variablen überschreiben config.yaml. Ideal für Docker.

---

## 8. Projektstruktur

```
aria/
├── Dockerfile
├── docker-compose.yml          # Nur ARIA (kein LLM, kein Qdrant)
├── pyproject.toml              # Dependencies
├── README.md
│
├── aria/                       # Python Package
│   ├── __init__.py
│   ├── main.py                 # FastAPI App + Startup
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── pipeline.py         # Hauptpipeline (6 Schritte)
│   │   ├── router.py           # Stufenmodell (Keyword → Embedding → LLM)
│   │   ├── context.py          # Context Assembler + Token-Budget
│   │   ├── llm_client.py       # LiteLLM Wrapper
│   │   ├── prompt_loader.py    # Lädt und cached Prompt-Files
│   │   ├── token_tracker.py    # Token-Logging + Stats
│   │   └── config.py           # Pydantic Settings
│   │
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── base.py             # BaseSkill ABC
│   │   ├── memory.py           # Qdrant Memory
│   │   ├── documents.py        # Datei-Reader
│   │   ├── web_search.py       # SearXNG
│   │   └── home.py             # Home Assistant (Phase 2)
│   │
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── base.py             # BaseChannel ABC
│   │   ├── web.py              # Eingebautes Web-UI
│   │   ├── discord.py          # Discord Bot
│   │   └── api.py              # OpenAI-kompatibler Endpoint
│   │
│   └── templates/              # Jinja2 HTML-Templates
│       ├── base.html
│       ├── chat.html
│       └── stats.html
│
├── prompts/                    # Prompt-Files (vom User anpassbar)
│   ├── persona.md
│   ├── skills/
│   │   ├── web_search.md
│   │   ├── memory.md
│   │   ├── documents.md
│   │   └── home.md
│   └── examples/
│       ├── persona_butler.md
│       ├── persona_coder.md
│       └── persona_minimal.md
│
├── config/
│   ├── config.yaml             # Hauptkonfiguration
│   └── config.example.yaml     # Template für neue User
│
├── data/                       # Persistente Daten (Docker Volume)
│   ├── logs/
│   │   └── tokens.jsonl
│   └── documents/              # Hochgeladene Dateien
│
└── tests/
    ├── test_router.py
    ├── test_pipeline.py
    └── test_skills.py
```

---

## 9. Datenfluss — Vollständiges Beispiel

```
User (Web UI): "Erinnerst du dich an mein NAS-Setup? Und such mal ob Proxmox 9 schon draussen ist."

1. WebChannel empfängt → pipeline.process()

2. Router (Stufenmodell):
   Stufe 1: "erinnerst" → memory_recall (partial match)
   Stufe 1: "such" → web_search (partial match)
   → Multi-Intent erkannt via Keywords: [memory_recall, web_search]
   → Kosten: 0 Tokens ✓

3. Skill Executor (parallel):
   
   Memory Skill:
   → Embedding: "NAS-Setup" → Vektor
   → Qdrant Search: Top 3 Treffer
   → Result: "NAS IP: 172.31.10.100, Proxmox Cluster auf ubnsrv-aiagent"
   
   Web Search Skill:
   → SearXNG: "Proxmox 9 release"
   → Top 5 Resultate, gekürzt auf 1500 chars

4. Context Assembler:
   System: "Du bist Reginald, direkt, schweizerisches Hochdeutsch..." (~200 Tokens)
   User: "Kontext:
     --- erinnerung ---
     NAS IP: 172.31.10.100, Proxmox Cluster auf ubnsrv-aiagent
     --- web_search ---
     [1] Proxmox VE 9.0 Release Notes...
     [2] Proxmox 9 neue Features...
     
     Frage: Erinnerst du dich an mein NAS-Setup?
     Und such mal ob Proxmox 9 schon draussen ist."

5. LLM (qwen3:8b):
   → "Ja, dein NAS läuft auf 172.31.10.100 im Proxmox-Cluster.
      Proxmox VE 9.0 ist seit [Datum] verfügbar. Wichtigste
      Neuerungen: [...]"

6. Token Tracker:
   → {prompt: 487, completion: 156, total: 643,
      intents: ["memory_recall", "web_search"],
      router_level: 1, source: "web"}

7. Response → Web UI mit Token-Badge [643 tokens]
```

---

## 10. Umsetzungsplan — Phasen

### Phase 1: Core + Memory + Chat ⏱️ ~2-3 Sessions

| # | Aufgabe | Details |
|---|---|---|
| 1.1 | Projektstruktur erstellen | pyproject.toml, Ordner, __init__.py |
| 1.2 | Config-System | Pydantic Settings + config.yaml + ENV Override |
| 1.3 | LLM Client | LiteLLM Wrapper, Chat + Classify |
| 1.4 | Prompt Loader | persona.md + skills/*.md laden/cachen |
| 1.5 | Router (Stufe 1: Keywords) | Keyword-Dict, Intent-Matching |
| 1.6 | Memory Skill (Qdrant) | Store + Recall + Embedding |
| 1.7 | Pipeline | 6-Schritte-Flow verdrahten |
| 1.8 | Context Assembler | Prompt-Builder mit Token-Budget |
| 1.9 | Token Tracker | JSONL-Logging |
| 1.10 | REST API Channel | POST /v1/chat/completions |
| 1.11 | Test: curl → ARIA → Memory → LLM → Antwort | End-to-End |

**Ergebnis Phase 1:** ARIA antwortet auf Chat, speichert/erinnert Dinge via Qdrant, loggt Tokens. Testbar via curl/API.

### Phase 2: Connections-Ausbau ⏱️ iterativ

Stand Maerz 2026:
- `SSH` ist bereits umgesetzt und dient als Referenz für weitere Connection-Typen.
- erste Connection-Welle ist als Config-/Health-Schicht umgesetzt:
  - `Discord`
  - `SFTP`
  - `SMB`
  - `Webhook`
  - `Email`
  - `HTTP API`
  - `RSS`
  - `MQTT`
- Nächste priorisierte Connections:
  1. `Discord`
  2. `SFTP / SMB`
  3. `Webhook`
  4. `Email`
  5. `HTTP API`
  6. `RSS`
  7. `MQTT`
- Ziel:
  - gleicher klarer UI-/Config-Stil wie bei `SSH`
  - einfache Konfiguration im Browser
  - saubere Einbindung in Skills (`source -> process -> target`)
  - keine unnötige Plattform-Komplexitaet
- nächster Ausbau innerhalb Phase 2:
  - konkrete Skill-/Runtime-Nutzung pro Connection-Typ schrittweise nachziehen
  - grosse E2E-Testsession für alle Connection-Typen

| # | Aufgabe | Details |
|---|---|---|
| 2.1 | Discord Connection | Notification-/Output-Ziel für Skills |
| 2.2 | SFTP / SMB Connections | Datei-Zugriff / Transfer |
| 2.3 | Webhook Connection | einfacher HTTP Push für Integrationen |
| 2.4 | Email Connection | Reports / Benachrichtigungen |
| 2.5 | HTTP API Connection | generische API-Anbindung |
| 2.6 | RSS Connection | Feed-Ingest / Monitoring |
| 2.7 | MQTT Connection | Event-/IoT-Integrationen |

**Ergebnis Phase 2:** ARIA kann über mehrere schlanke, klar konfigurierbare Connections mit externen Systemen arbeiten.

### Phase 2B: Dokumente + Wissens-Ingest ⏱️ eigener Block

| # | Aufgabe | Details |
|---|---|---|
| 2B.1 | Dokument-Ingest | Upload / Einlesen von `txt`, `md`, `pdf` |
| 2B.2 | Chunking + Embeddings | Vorbereitung für semantische Suche |
| 2B.3 | Collection-Strategie | neue / bestehende / pro User |
| 2B.4 | Retrieval-Pfad | Knowledge-Recall sauber neben Memory |

**Wichtig:** Dokumente/RAG sind bewusst **kein normaler Skill**, sondern ein eigenes Wissens-Feature.

### Phase 3: Web UI ⏱️ ~1-2 Sessions

| # | Aufgabe | Details |
|---|---|---|
| 3.1 | HTML Templates (Jinja2 + HTMX) | Chat-Interface |
| 3.2 | WebSocket/SSE für Streaming | Live-Antworten |
| 3.3 | Token-Badge pro Nachricht | Transparenz |
| 3.4 | Stats-Seite | Token-Verbrauch über Zeit |
| 3.5 | Dark Mode + Mobile | CSS |

**Ergebnis Phase 3:** Schlankes Web-UI, keine externe Abhängigkeit.

### Phase 4: Channels + Distribution ⏱️ ~1-2 Sessions

| # | Aufgabe | Details |
|---|---|---|
| 4.1 | Discord Channel | discord.py Adapter |
| 4.2 | OpenAI-kompatibler Endpoint | Für OpenWebUI-Anbindung |
| 4.3 | Dockerfile | Multi-Stage Build, minimal Image |
| 4.4 | docker-compose.yml | Volumes, ENV, Health Check |
| 4.5 | README.md | Quickstart, Config-Doku |
| 4.6 | GitHub Repo | CI/CD, Docker Hub Push |

**Ergebnis Phase 4:** `docker pull aria` → `docker run aria` → läuft.

### Phase 5: Smart Home + Extras ⏱️ Nach Bedarf

| # | Aufgabe | Details |
|---|---|---|
| 5.1 | Home Assistant Skill | Entity-Steuerung mit Whitelist |
| 5.2 | Router Stufe 2 | Embedding-basierte Klassifikation |
| 5.3 | Cron-Jobs | Tägliche Zusammenfassungen |
| 5.4 | Konversationshistorie | Letzte N Nachrichten mitsenden |
| 5.5 | SQLite Memory Fallback | Für User ohne Qdrant |
| 5.6 | Plugin-System | Community Skills via pip install |

---

## 11. Modellstrategie

| Aufgabe | Modell | Temp | max_tokens | Begründung |
|---|---|---|---|---|
| Chat + Zusammenfassung | qwen3:8b | 0.4 | 1024 | Besser als qwen2.5, Thinking-Modus |
| Intent-Klassifikation (Stufe 3) | qwen3:8b /no_think | 0.1 | 200 | Schnell, deterministisch |
| Embeddings | nomic-embed-text | — | — | Schnell, läuft auf Mac M2 |
| Fallback (optional) | via LiteLLM/OpenRouter | — | — | Wenn User Cloud-Modelle will |

**Qwen3:8b Besonderheiten:**
- Thinking-Modus: Für komplexe Anfragen (Chat) → `merge_reasoning_content_in_choices: true` in LiteLLM
- No-Think-Modus: Für Klassifikation → `/no_think` Suffix oder `temperature=0.1`
- Kontext: 32k native, 131k mit YaRN — mehr als genug für ARIA's schlanke Prompts

---

## 12. Sicherheit

| Massnahme | Details |
|---|---|
| HA Entity-Whitelist | Nur konfigurierte Entities steuerbar |
| Datei-Pfad-Whitelist | Nur `allowed_paths` aus config.yaml |
| Channel-Auth | Discord: User-Whitelist. API: Bearer Token |
| Kein Agent-Loop | LLM kann nie selbständig Tools aufrufen |
| Input-Sanitierung | Prompt-Injection-Schutz im Context Assembler |
| Token-Logging | Ungewöhnlicher Verbrauch erkennbar |
| Keine Cloud-Default | Alles lokal, Cloud nur wenn User es konfiguriert |

---

## 13. Abhängigkeiten (minimal)

```toml
[project]
name = "aria-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "litellm>=1.55",
    "qdrant-client>=1.12",
    "aiofiles>=24.1",
    "jinja2>=3.1",
    "pyyaml>=6.0",
    "httpx>=0.28",
    "pydantic-settings>=2.7",
]

[project.optional-dependencies]
discord = ["discord.py>=2.4"]
documents = ["pdfplumber>=0.11"]
```

**Bewusst NICHT dabei:**
- Kein LangChain (Overhead, Abstraktion die wir nicht brauchen)
- Kein Mem0 (Blackbox, JSON-Parsing-Probleme)
- Kein React/Node.js (HTMX reicht)
- Kein SQLAlchemy (JSONL + Qdrant reicht)

---

## 14. Docker

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY aria/ aria/
COPY prompts/ prompts/
COPY config/config.example.yaml config/config.yaml

EXPOSE 8800

VOLUME ["/app/config", "/app/prompts", "/app/data"]

HEALTHCHECK CMD curl -f http://localhost:8800/health || exit 1

CMD ["uvicorn", "aria.main:app", "--host", "0.0.0.0", "--port", "8800"]
```

### docker-compose.yml (für User)

```yaml
services:
  aria:
    image: ghcr.io/fischerman/aria:latest
    ports:
      - "8800:8800"
    volumes:
      - ./config:/app/config
      - ./prompts:/app/prompts
      - ./data:/app/data
    environment:
      - ARIA_LLM_API_BASE=http://host.docker.internal:11434
      - ARIA_QDRANT_URL=http://host.docker.internal:6333
    restart: unless-stopped
```

**Für User ohne Qdrant:**

```yaml
environment:
  - ARIA_MEMORY_BACKEND=sqlite  # Fallback, läuft ohne Qdrant
```

---

## 15. Was ARIA NICHT ist

- **Kein Agent-Loop-System** — kein LangChain, kein CrewAI, kein AutoGPT
- **Kein Coding-Agent** — dafür gibt es Codex/Roo Code
- **Kein Token-Verschwender** — jeder Request ist budgetiert
- **Keine Cloud-Abhängigkeit** — alles lokal, Cloud ist opt-in
- **Kein Monolith** — Skills sind austauschbar, Channels sind austauschbar

---

## 16. Zusammenfassung

```
User → Channel (Web/Discord/API)
  → Pipeline:
    1. Prompt-Files laden (gecached)
    2. Router (Keywords → Embedding → LLM, stufenweise)
    3. Skills ausführen (parallel)
    4. Kontext zusammenbauen (Token-Budget)
    5. LLM aufrufen (1 Call)
    6. Token-Verbrauch loggen
  → Antwort zurück

~900-1200 Tokens pro Request (vs. 8000-15000 bei OpenClaw)
~70% der Requests: 0 Router-Tokens (Keyword-Match)
1 Docker Container, 1 config.yaml, läuft.
```

---

## 17. Nächster Schritt

Phase 1 starten. Dafür brauchen wir:

| Info | Für was | Bekannt? |
|---|---|---|
| Mac Ollama IP | LLM + Embeddings | 172.31.100.15 ✓ |
| LiteLLM | Proxy (optional) | 172.31.10.210:4000 ✓ |
| Qdrant | Memory | Port 6333, IP? |
| SearXNG | Websuche (Phase 2) | IP + Port? |
| Wo soll ARIA laufen? | Docker Host | ubnsrv-aiagent? |

Codex oder Roo Code können den Grossteil des Codes generieren. Wir liefern die Architektur, die AI schreibt den Code.
