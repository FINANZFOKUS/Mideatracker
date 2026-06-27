"""Gemeinsame Infrastruktur für alle Quellen-Adapter."""

from __future__ import annotations

import logging
import random
import re
import time

import requests

log = logging.getLogger(__name__)

# Realistische Browser-Header – viele Shops blocken sonst mit HTTP 403.
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Zeitbudgets bewusst knapp, damit ein 10-Minuten-Lauf nicht überzogen wird.
DEFAULT_TIMEOUT = 15  # Sekunden pro HTTP-Request
BROWSER_GOTO_MS = 15000  # Seitenaufbau im Browser-Fallback
BROWSER_SELECTOR_MS = 6000  # Warten auf Selektor (kurz – fehlt er, geht's ohne)


def browser_headers(extra: dict | None = None) -> dict:
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if extra:
        headers.update(extra)
    return headers


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(browser_headers())
    return s


def http_get(
    url: str,
    *,
    session: requests.Session | None = None,
    headers: dict | None = None,
    params: dict | None = None,
    retries: int = 2,
    timeout: int = DEFAULT_TIMEOUT,
) -> requests.Response | None:
    """GET mit Retry/Backoff. Gibt None zurück, wenn dauerhaft fehlschlägt.

    Bei dauerhaftem Block (403/404/451) wird nicht weiter wiederholt – ein
    erneuter Versuch ändert daran nichts und kostet nur Zeit.
    """
    sess = session or get_session()
    for attempt in range(retries):
        try:
            resp = sess.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp
            log.warning("GET %s -> HTTP %s (Versuch %d)", url, resp.status_code, attempt + 1)
            if resp.status_code in (403, 404, 451):
                break  # Block/„nicht da“ – Retry zwecklos, direkt zum Fallback
        except requests.RequestException as exc:
            log.warning("GET %s fehlgeschlagen: %s (Versuch %d)", url, exc, attempt + 1)
        if attempt < retries - 1:
            time.sleep(min(2 ** attempt + random.random(), 3))
    return None


def http_get_json(url: str, **kwargs) -> dict | list | None:
    resp = http_get(url, **kwargs)
    if resp is None:
        return None
    try:
        return resp.json()
    except ValueError:
        log.warning("Antwort von %s ist kein gültiges JSON.", url)
        return None


def fetch_html_via_browser(
    url: str,
    *,
    wait_selector: str | None = None,
    timeout_ms: int = BROWSER_GOTO_MS,
) -> str | None:
    """Fallback für bot-feindliche Seiten: echte Browser-Session via Playwright.

    Nutzt – falls vorhanden – den in CI vorinstallierten Chromium. Schlägt der
    Import oder Start fehl, wird None zurückgegeben (Adapter überspringt dann).
    Die Timeouts sind knapp gehalten, damit der Gesamtlauf zügig bleibt.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.info("Playwright nicht installiert – Browser-Fallback für %s übersprungen.", url)
        return None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                locale="de-DE",
            )
            page = ctx.new_page()
            page.set_default_timeout(BROWSER_SELECTOR_MS)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception:  # noqa: BLE001 - langsame/blockierende Seite
                pass
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=BROWSER_SELECTOR_MS)
                except Exception:  # noqa: BLE001 - Selektor optional
                    pass
            html = page.content()
            browser.close()
            return html
    except Exception as exc:  # noqa: BLE001 - Browser-Fallback ist best effort
        log.warning("Browser-Fallback für %s fehlgeschlagen: %s", url, exc)
        return None


_PRICE_RE = re.compile(r"(\d{1,3}(?:[.\s]\d{3})*|\d+)(?:[,.](\d{2}))?")


def parse_price(text: str) -> float | None:
    """Extrahiert einen EUR-Preis aus deutschem Text (z.B. '1.299,00 €')."""
    if not text:
        return None
    cleaned = text.replace("\xa0", " ")
    m = _PRICE_RE.search(cleaned)
    if not m:
        return None
    whole = m.group(1).replace(".", "").replace(" ", "")
    cents = m.group(2) or "00"
    try:
        return float(f"{whole}.{cents}")
    except ValueError:
        return None
