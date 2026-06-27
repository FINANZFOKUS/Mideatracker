"""Baumarkt-Adapter für OBI, Bauhaus und Hornbach (gemeinsamer Code).

Diese Shops blocken einfache Requests mit HTTP 403, betten aber strukturierte
Produktdaten (JSON-LD) ein. Wir versuchen daher zuerst einen normalen Request
und fallen bei Block auf eine echte Browser-Session (Playwright/Chromium)
zurück. Geliefert wird die Online-Verfügbarkeit; Filialabholung kann später
ergänzt werden.
"""

from __future__ import annotations

import logging

from ..config import Config
from ..models import CHANNEL_ONLINE, CONDITION_NEW, Offer
from .base import fetch_html_via_browser, http_get
from .buyability import assess_buyability
from .jsonld import extract_products

log = logging.getLogger(__name__)

_LABEL = {"obi": "OBI", "bauhaus": "BAUHAUS", "hornbach": "Hornbach"}


def _html(url: str) -> str | None:
    resp = http_get(url)
    if resp is not None and resp.status_code == 200:
        return resp.text
    # 403/Block erwartet -> echter Browser.
    log.info("Baumarkt-Seite direkt nicht erreichbar – versuche Browser-Fallback.")
    return fetch_html_via_browser(url, wait_selector="script[type='application/ld+json']")


def fetch_offers(cfg: Config, chain: str = "obi") -> list[Offer]:
    url = cfg.url_for(chain)
    if not url:
        log.info("%s: keine Produkt-URL konfiguriert – übersprungen.", chain)
        return []

    html = _html(url)
    if not html:
        return []

    product_ean = cfg.product.eans[0] if cfg.product.eans else None
    label = _LABEL.get(chain, chain.capitalize())
    offers: list[Offer] = []
    for prod in extract_products(html):
        if prod["price"] is None:
            continue
        # Strikte Kaufbarkeit: strukturiertes InStock (kein InStoreOnly) UND
        # kein negativer Marker auf der Seite.
        buyable, signals = assess_buyability(html, jsonld_in_stock=prod["in_stock"])
        log.info(
            "%s: availability=%s -> bestellbar=%s %s",
            chain, prod.get("availability_raw"), buyable, signals,
        )
        offers.append(
            Offer(
                source=chain,
                title=prod["title"] or cfg.product.name,
                price=prod["price"],
                url=url,
                in_stock=buyable,
                condition=CONDITION_NEW,
                channel=CHANNEL_ONLINE,
                ean=prod["ean"] or product_ean,
                merchant=label,
            )
        )

    log.info("%s: %d Angebote extrahiert.", chain, len(offers))
    return offers
