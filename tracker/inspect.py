"""Diagnose: zeigt pro Shop die echten Kaufbarkeits-Signale.

Aufruf (idealerweise in GitHub Actions, da Shops dort erreichbar sind):
    python -m tracker.inspect

Gibt je konfigurierter Quelle aus: Abrufweg, gefundene JSON-LD-Angebote
(Preis/EAN/availability) und die Kaufbarkeits-Bewertung inkl. Signale. Dient
dazu, die Adapter präzise zu kalibrieren (Pseudo-Treffer vermeiden).
"""

from __future__ import annotations

import logging

import re

from .config import load_config
from .sources.base import fetch_html_via_browser, http_get
from .sources.buyability import assess_buyability
from .sources.jsonld import extract_products

log = logging.getLogger(__name__)

SELECTOR = "script[type='application/ld+json']"

# Schlüssel, deren Umgebung in eingebettetem JSON die echten Feldnamen für
# Preis/Verfügbarkeit verrät (für SPA-Shops ohne schema.org).
_SIGNAL_KEYS = (
    "availability",
    "onlineavailab",
    "deliverabilit",
    "shippingavail",
    "stockstatus",
    "instock",
    "orderable",
    "purchasable",
    "buyable",
    '"price"',
)


def _dump_embedded_signals(html: str, *, max_per_key: int = 2, window: int = 90) -> None:
    """Zeigt kurze Ausschnitte rund um aussagekräftige JSON-Schlüssel.

    Hilft, die echten Feldnamen für Preis/Verfügbarkeit in SPA-Seiten
    (MediaMarkt/Saturn/Bauhaus) zu lokalisieren, ohne 1 MB HTML zu drucken.
    """
    low = html.lower()
    for key in _SIGNAL_KEYS:
        count = 0
        start = 0
        while count < max_per_key:
            idx = low.find(key, start)
            if idx == -1:
                break
            snippet = html[max(0, idx - 15): idx + window]
            snippet = re.sub(r"\s+", " ", snippet)
            print(f"    ~{key}: …{snippet}…")
            start = idx + len(key)
            count += 1


def _fetch(url: str) -> tuple[str | None, str]:
    resp = http_get(url, retries=2)
    if resp is not None and resp.status_code == 200:
        return resp.text, "direct"
    html = fetch_html_via_browser(url, wait_selector=SELECTOR)
    return html, "browser-fallback" if html else "failed"


def inspect() -> int:
    cfg = load_config()
    print(f"=== Diagnose für '{cfg.product.name}' (EAN {cfg.product.eans}) ===\n")

    for source in cfg.enabled_sources():
        url = cfg.url_for(source)
        if not url:
            print(f"[{source}] keine URL konfiguriert – übersprungen\n")
            continue

        print(f"[{source}] {url}")
        html, how = _fetch(url)
        print(f"  Abruf: {how}")
        if not html:
            print("  -> kein HTML erhalten\n")
            continue

        print(f"  HTML-Länge: {len(html)} Zeichen")
        products = extract_products(html)
        if not products:
            print("  JSON-LD: keine Product-Angebote gefunden")
        for p in products:
            print(
                f"  JSON-LD: title={p['title'][:50]!r} ean={p['ean']} "
                f"price={p['price']} availability={p.get('availability_raw')}"
            )

        jsonld_in_stock = any(p["in_stock"] for p in products)
        buyable, signals = assess_buyability(html, jsonld_in_stock=jsonld_in_stock)
        print(f"  Kaufbarkeit: {'JA' if buyable else 'NEIN'}  signals={signals}")

        # Ohne schema.org: eingebettete JSON-Signale zeigen (SPA-Shops).
        if not products:
            print("  Eingebettete Signale:")
            _dump_embedded_signals(html)
        print()

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(inspect())
