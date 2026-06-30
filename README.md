# Midea PortaSplit 12.000 BTU – Verfügbarkeits-Tracker

Prüft alle ~10 Minuten automatisch mehrere Quellen auf ein **wirklich
bestellbares** Angebot der **Midea PortaSplit 12.000 BTU** (EAN
`4048164116478`) unter **800 €** – online **und** in Märkten im **25-km-Umkreis
von 74321 Bietigheim-Bissingen** – und schickt bei einer **neuen
Verfügbarkeit** eine **Telegram-Push** mit direktem Kauf-Link.

Läuft kostenlos über **GitHub Actions** – kein eigener Server, keine App-
Installation nötig (außer Telegram auf dem Handy).

## Wie es funktioniert

```
GitHub Actions (alle 10 Min)
  → Quellen abfragen (Geizhals/Idealo, MediaMarkt/Saturn, OBI/Bauhaus/Hornbach, Amazon + Warehouse)
  → Filter "nur wirklich bestellbar"
  → Diff gegen letzten Lauf (kein Spam)
  → Telegram-Push bei neuem Treffer
```

### Filter „nur wirklich bestellbar"
Ein Angebot alarmiert nur, wenn **alle** Bedingungen erfüllt sind
(`tracker/matching.py` + `tracker/sources/buyability.py`):
1. **Richtiges Produkt** – EAN `4048164116478` (oder, ohne EAN, Titelabgleich
   auf „portasplit"). Hinweis: Das Gerät ist Comfee-gebrandet („Midea Comfee
   PortaSplit"), daher wird „comfee" **nicht** ausgeschlossen.
2. **Wirklich online bestellbar** – strenge Prüfung: nur strukturiertes
   schema.org `InStock`/`OnlineOnly` zählt. `InStoreOnly` (nur im Markt
   vorrätig) zählt **nicht**; negative Marker („ausverkauft", „nur im Markt",
   „nicht verfügbar") sind ein Veto; generische Seitentexte wie „in den
   Warenkorb" gelten **nicht** als Beweis. Lieber ein Deal verpasst als ein
   Pseudo-Alarm (nächster Check in 10 Min).
3. **Preis ≤ 800 €**.
4. **Zustand** – neu immer; gebraucht (Amazon Warehouse) nur weil `allow_used: true`.
5. **Filialen** – nur innerhalb von 25 km.

### Shop-Abdeckung (Stand der Live-Tests)
| Shop | Status |
|---|---|
| **OBI** | ✅ direkt erreichbar, sauberes schema.org → meldet bei echter Online-Verfügbarkeit (aktuell `InStoreOnly`) |
| **MediaMarkt / Saturn** | ✅ eingebettetes JSON (an Produkt-ID gekoppelt) wird geparst → meldet bei echtem Direkt-Angebot < 800 €. Aktuell nur Marketplace-Angebot ~2.589 € (fällt korrekt raus) |
| **Hornbach** | 🔓 Bot-Wall via Stealth-Browser überwunden (volle Seite), aber Preis/Verfügbarkeit werden erst per Client-API nachgeladen → bräuchte zusätzliches API-Parsing (zurückgestellt) |
| **Bauhaus** | ⚠️ erreichbar, aber nur Analytics-Daten eingebettet → kein verlässliches Preis/Verfügbarkeits-Signal (zurückgestellt) |
| **Geizhals** | ✅ kein JSON-LD, aber Bestpreis wird aus `og:title`/`gh_price` geparst (`tracker/sources/geizhals.py`) → meldet bei echtem Bestpreis < 800 € über alle gelisteten Shops |
| **Idealo / Amazon** | ❌ hart geblockt (Bot-Wall hält auch mit Stealth, da Datacenter-IP) – bräuchte Residential-Proxy (zurückgestellt) |

**Stealth-Fähigkeit:** Der Browser-Fallback (`tracker/sources/base.py`) verschleiert
Automations-Merkmale und löst JS-Challenges auf; `fetch_page()` erkennt auch
HTTP-200-Bot-Walls. Damit ist Hornbach erreichbar und OBI/MediaMarkt/Saturn robuster.

Diagnose jederzeit per Workflow **„Diagnose Shops"** (`inspect.yml`), Funktionstest
der Push per **„Test-Alarm senden"** (`test-notify.yml`).

### Heartbeat & Totalausfall-Alarm
Damit kein stiller Ausfall unbemerkt bleibt, schickt der Tracker:
- **1×/Tag** eine **„lebt noch"-Statusmeldung** (günstigster Preis je Gerät,
  „Quellen mit Daten X/Y", Anzahl bestellbarer Treffer) – ab `heartbeat.hour_utc`.
- einen **Sofort-Alarm bei Totalausfall**, wenn in einem Lauf **keine einzige**
  Quelle Daten liefert (z.B. alle geblockt) – sonst entsteht falsche Sicherheit.

Beides ist auf max. 1×/Tag entprellt (Datumsmarken in `state.json`) und in
`config.yaml` unter `heartbeat:` ein-/ausschaltbar.

### Tests / CI
Die Test-Suite läuft netzwerkfrei (`python -m pytest -q`) und bei jedem Push/PR
automatisch über den Workflow **CI (Tests)** (`.github/workflows/ci.yml`).

## Einrichtung (einmalig)

### 1. Telegram-Bot anlegen
1. In Telegram **@BotFather** öffnen → `/newbot` → Namen vergeben → du erhältst
   einen **Bot-Token** (`123456:ABC...`).
2. Schreibe deinem neuen Bot eine beliebige Nachricht (z.B. „hi").
3. **Chat-ID ermitteln:** Öffne im Browser
   `https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates` und lies `chat.id` aus.

### 2. GitHub Secrets hinterlegen
Im Repo unter **Settings → Secrets and variables → Actions → New repository secret**:
- `TELEGRAM_BOT_TOKEN` = dein Bot-Token
- `TELEGRAM_CHAT_ID` = deine Chat-ID

> Der Token liegt damit verschlüsselt bei GitHub, **nie** im Code. Daher kann
> das Repo **öffentlich** sein → unbegrenzte Actions-Minuten für den 10-Min-Takt.
> (Privates Repo: 2.000 Min/Monat – ggf. Intervall in `check.yml` auf `*/15` erhöhen.)

### 3. Produkte & URLs eintragen (`config.yaml`)
Die **Watchlist** (`products:`) kann beliebig viele Geräte enthalten – jeder
Eintrag bringt seine eigenen Shop-URLs (`urls:`) mit. Die globalen Blöcke
`location` und `sources` gelten für alle Produkte.

```yaml
products:
  - name: "Midea PortaSplit 12.000 BTU"
    eans: ["4048164116478"]
    title_must_include: ["portasplit"]
    title_must_exclude: ["comfee"]
    max_price: 800.0
    allow_used: true
    urls:
      idealo: "https://www.idealo.de/preisvergleich/OffersOfProduct/XXXXXXXX.html"
      mediamarkt: "https://www.mediamarkt.de/de/product/_midea-portasplit-XXXXXXX.html"
      obi: "https://www.obi.de/p/8620890/..."
      amazon: "https://www.amazon.de/dp/B0D3PP64JS"
  # - name: "Weiteres Gerät"
  #   eans: ["..."]
  #   ...
  #   urls: { idealo: "..." }
```

> Leere/fehlende URLs werden je Produkt übersprungen. Quellen, die du gar nicht
> nutzen willst, unter `sources:` auf `false` setzen. Das **alte Format**
> (`product:` + globaler `source_urls:`-Block) wird weiterhin geladen.

### 4. Filialen im Umkreis auflösen (`stores.yaml`, optional)
Für **Filial-Bestand** bei MediaMarkt/Saturn die Märkte im 25-km-Umkreis
(z.B. Ludwigsburg, Stuttgart) mit Koordinaten und ketteninterner **Store-ID**
eintragen. `stores.yaml` ist mit den Filialen vorbefüllt – es fehlen nur die
IDs:

1. Store-Finder öffnen: `https://www.mediamarkt.de/de/storefinder`
2. Filiale wählen; die Zahl am Ende der Store-URL (`…/store/<NAME>-<ID>`) ist
   die ID → bei `id:` in `stores.yaml` eintragen.

Ein Eintrag **ohne ID** ist erlaubt: die Filiale wird dann übersprungen (kein
Fehlalarm), die Distanz aber bereits aus den Koordinaten berechnet. Ohne
nutzbare Einträge wird nur die **Online-Verfügbarkeit** geprüft (die i.d.R.
wichtigste).

> **Status Filialbestand (best effort):** Die MediaMarkt/Saturn-Bestands-API
> sitzt hinter einer WAF. Der Adapter ruft sie daher über eine echte
> Browser-Session ab (`fetch_json_via_browser`) mit den korrekten PWA-Headern –
> damit kommt er an der HTTP-403-Bot-Wall vorbei (verifiziert: API antwortet
> 200). Der `persistedQuery`-Hash (`_AVAIL_QUERY_HASH` in
> `tracker/sources/mediamarkt.py`) **rotiert mit jedem PWA-Release**; ist er
> veraltet, kommt `PersistedQueryNotFound` und es gibt schlicht keinen
> Filialtreffer. Aktuellen Hash nachtragen: Produktseite → DevTools → Netzwerk
> (Filter `graphql`) → „Verfügbarkeit im Markt" prüfen → den `sha256Hash` aus
> dem `GetProductAvailabilities`-Request kopieren. Die **Online-Verfügbarkeit**
> bleibt davon unberührt und ist der zuverlässige Teil.

## Lokal testen

```bash
pip install -r requirements.txt

# Trockenlauf: zeigt gefundene Angebote + Telegram-Vorschau, sendet nichts
python -m tracker.run --dry-run -v

# Telegram-Test (Secrets als ENV setzen)
export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
python -m tracker.notify --test

# Tests
python -m pytest -q
```

## Scharf schalten
Sind Secrets und mindestens eine Produkt-URL gesetzt, läuft der Workflow
automatisch alle 10 Minuten. Manuell anstoßen: **Actions → „Midea PortaSplit
Verfügbarkeit" → Run workflow**. Sobald das Gerät unter 800 € bestellbar ist,
kommt die Push aufs Handy.

## Hinweise
- Rein **privater** Gebrauch, niedrige Frequenz, klarer User-Agent. Manche
  Shops blocken Bots – dafür gibt es einen **Browser-Fallback** (Playwright/
  Chromium), der in GitHub Actions automatisch genutzt wird.
- Fällt eine Quelle aus, laufen die anderen weiter (Fehler werden nur geloggt).
- Selektoren einzelner Shops können sich ändern; primär werden stabile
  **schema.org-JSON-LD-Daten** genutzt (`tracker/sources/jsonld.py`).
