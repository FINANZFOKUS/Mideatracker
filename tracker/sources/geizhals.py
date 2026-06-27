"""Geizhals-Adapter (Preisvergleich).

Geizhals listet pro Produkt mehrere Händlerangebote. Wir lesen primär die
JSON-LD-Angebotsdaten der Produktseite; zusätzlich versuchen wir die
Händler-Angebotszeilen aus dem HTML zu parsen. Bei Block (403) greift der
Browser-Fallback.
"""

from __future__ import annotations

import logging

from ..config import Config
from ..models import CHANNEL_ONLINE, CONDITION_NEW, Offer
from .base import fetch_html_via_browser, http_get
from .jsonld import extract_products

log = logging.getLogger(__name__)

SOURCE = "geizhals"


def _html(url: str) -> str | None:
    resp = http_get(url)
    if resp is not None:
        return resp.text
    log.info("Geizhals direkt geblockt – versuche Browser-Fallback.")
    return fetch_html_via_browser(url, wait_selector="script[type='application/ld+json']")


def fetch_offers(cfg: Config) -> list[Offer]:
    url = cfg.url_for(SOURCE)
    if not url:
        log.info("Geizhals: keine Produkt-URL konfiguriert – übersprungen.")
        return []

    html = _html(url)
    if not html:
        return []

    offers: list[Offer] = []

    # Nur strukturierte Daten (Titel/EAN/Preis/Verfügbarkeit). Wir stempeln
    # bewusst NICHT unser Produkt auf unbekannte Zeilen – sonst könnte die
    # (teurere) Comfee-Variante einen Pseudo-Treffer erzeugen. Der strikte
    # Produkt-/Preisfilter (matching.is_buyable) entscheidet anschließend.
    for prod in extract_products(html):
        if prod["price"] is None:
            continue
        offers.append(
            Offer(
                source=SOURCE,
                title=prod["title"] or cfg.product.name,
                price=prod["price"],
                url=url,
                in_stock=prod["in_stock"],
                condition=CONDITION_NEW,
                channel=CHANNEL_ONLINE,
                ean=prod["ean"],  # kein Fallback-Stempel → Titel-Ausschluss greift
                merchant="Geizhals (Bestpreis)",
            )
        )

    log.info("Geizhals: %d Angebote extrahiert.", len(offers))
    return offers
