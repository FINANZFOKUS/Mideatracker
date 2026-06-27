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
1. **Richtiges Produkt** – EAN `4048164116478` (oder strikter Titelabgleich,
   schließt die teure Alt-Variante „Comfee" aus).
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
| **OBI** | ✅ direkt erreichbar, sauberes schema.org → meldet bei echter Online-Verfügbarkeit |
| **Saturn** | ⚠️ erreichbar, aktuell „ausverkauft" → wird gemeldet sobald wieder bestellbar |
| **MediaMarkt / Bauhaus** | ⚠️ erreichbar, aber SPA ohne schema.org → braucht Parsing der eingebetteten JSON-Daten (Ausbau) |
| **Idealo / Hornbach / Amazon** | ❌ serverseitig hart geblockt (Bot-Wall, Mini-HTML) – aktuell ohne zuverlässige Daten |

Diagnose jederzeit per Workflow **„Diagnose Shops"** (`inspect.yml`), Funktionstest
der Push per **„Test-Alarm senden"** (`test-notify.yml`).

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

### 3. Produkt-URLs eintragen (`config.yaml`)
Trage je Quelle die direkte Produktseite ein (leere Werte werden übersprungen):

| Quelle | Beispiel-URL |
|---|---|
| `geizhals` | `https://geizhals.de/midea-portasplit-aXXXXXXX.html` |
| `idealo` | `https://www.idealo.de/preisvergleich/OffersOfProduct/XXXXXXXX.html` |
| `mediamarkt` | `https://www.mediamarkt.de/de/product/_midea-portasplit-XXXXXXX.html` |
| `saturn` | `https://www.saturn.de/de/product/_midea-portasplit-XXXXXXX.html` |
| `obi` | `https://www.obi.de/p/8620890/...` |
| `bauhaus` | `https://www.bauhaus.info/.../p/31934233` |
| `hornbach` | `https://www.hornbach.de/p/...` |
| `amazon` | `https://www.amazon.de/dp/B0D3PP64JS` |

> Die URLs findest du, indem du das Gerät (EAN `4048164116478`) im jeweiligen
> Shop suchst. Quellen, die du nicht nutzen willst, kannst du unter `sources:`
> auf `false` setzen.

### 4. Filialen im Umkreis auflösen (`stores.yaml`, optional)
Für **Filial-Bestand** bei MediaMarkt/Saturn die Märkte im 25-km-Umkreis
(z.B. Ludwigsburg, Stuttgart, Sindelfingen) mit ihrer ketteninternen
Store-ID und Koordinaten eintragen. Ohne Einträge wird nur die
**Online-Verfügbarkeit** geprüft (die i.d.R. wichtigste).

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
