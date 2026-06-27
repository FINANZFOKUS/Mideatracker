"""MediaMarkt-/Saturn-Adapter (gemeinsamer Code für beide Ketten).

Strategie:
  1. Online-Preis & -Verfügbarkeit robust aus der Produktseite (JSON-LD).
  2. Filial-Bestand (best effort) über das inoffizielle GraphQL-Endpoint
     ``GetProductAvailabilities`` für die in stores.yaml hinterlegten Märkte.

Hinweis: Das GraphQL-Endpoint nutzt rotierende "persisted query"-Hashes und
hat Anti-Bot-Schutz. Es kann zeitweise HTML statt JSON liefern; in dem Fall
fällt der Adapter still auf die Online-Daten zurück.
"""

from __future__ import annotations

import logging

from ..config import Config, Store
from ..models import CHANNEL_ONLINE, CHANNEL_STORE, CONDITION_NEW, Offer
from .base import browser_headers, fetch_html_via_browser, http_get, http_get_json
from .buyability import assess_buyability
from .jsonld import extract_products

log = logging.getLogger(__name__)

_DOMAINS = {"mediamarkt": "www.mediamarkt.de", "saturn": "www.saturn.de"}
_SALESLINE = {"mediamarkt": "Media", "saturn": "Saturn"}

# Rotierender persisted-query-Hash; bei Bedarf in der Quelle aktualisieren.
_AVAIL_QUERY_HASH = "810286f7ae9368cb54ccd122b21e453bd00ed7dbf534b8259b8bed68f8da999f"

_IN_STORE_TOKENS = {"IN_STORE", "IN_WAREHOUSE", "AVAILABLE", "PICKUP"}


def _product_html(url: str) -> str | None:
    resp = http_get(url)
    if resp is not None:
        return resp.text
    return fetch_html_via_browser(url, wait_selector="script[type='application/ld+json']")


def _online_offers(cfg: Config, chain: str, url: str) -> list[Offer]:
    html = _product_html(url)
    if not html:
        return []
    product_ean = cfg.product.eans[0] if cfg.product.eans else None
    offers: list[Offer] = []
    for prod in extract_products(html):
        if prod["price"] is None:
            continue
        buyable, signals = assess_buyability(html, jsonld_in_stock=prod["in_stock"])
        log.info(
            "%s online: availability=%s -> bestellbar=%s %s",
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
                merchant=chain.capitalize(),
            )
        )
    return offers


def _extract_product_id(url: str) -> str | None:
    """Item-Nummer aus einer MediaMarkt/Saturn-Produkt-URL (…-<id>.html)."""
    tail = url.rstrip("/").rsplit("-", 1)[-1]
    digits = "".join(ch for ch in tail if ch.isdigit())
    return digits or None


def _store_offers(cfg: Config, chain: str, url: str, online_price: float | None) -> list[Offer]:
    stores = cfg.stores_for(chain)
    product_id = _extract_product_id(url)
    if not stores or not product_id:
        return []

    domain = _DOMAINS[chain]
    endpoint = f"https://{domain}/api/v1/graphql"
    params = {
        "operationName": "GetProductAvailabilities",
        "variables": f'{{"ids":["{product_id}"]}}',
        "extensions": (
            '{"pwa":{"salesLine":"%s","country":"DE","language":"de"},'
            '"persistedQuery":{"version":1,"sha256Hash":"%s"}}'
            % (_SALESLINE[chain], _AVAIL_QUERY_HASH)
        ),
    }
    headers = browser_headers({"Accept": "application/json", "apollographql-client-name": "pwa"})
    data = http_get_json(endpoint, headers=headers, params=params)
    if not isinstance(data, dict):
        log.info("%s: Filial-API lieferte kein JSON – Filialbestand übersprungen.", chain)
        return []

    avails = (((data.get("data") or {}).get("availabilities")) or [])
    if not isinstance(avails, list):
        return []

    by_store: dict[str, dict] = {}
    for entry in avails:
        if isinstance(entry, dict):
            sid = str(entry.get("storeId") or entry.get("id") or "")
            if sid:
                by_store[sid] = entry

    offers: list[Offer] = []
    for store in stores:
        entry = by_store.get(store.id)
        if not entry:
            continue
        status = str(entry.get("availabilityType") or entry.get("status") or "").upper()
        if not any(tok in status for tok in _IN_STORE_TOKENS):
            continue
        offers.append(
            Offer(
                source=chain,
                title=cfg.product.name,
                price=online_price or cfg.product.max_price,
                url=url,
                in_stock=True,
                condition=CONDITION_NEW,
                channel=CHANNEL_STORE,
                ean=cfg.product.eans[0] if cfg.product.eans else None,
                merchant=chain.capitalize(),
                store_name=store.name,
                distance_km=_distance(cfg, store),
            )
        )
    return offers


def _distance(cfg: Config, store: Store) -> float | None:
    if store.distance_km is not None:
        return store.distance_km
    if store.lat is None or store.lon is None:
        return None
    from ..matching import haversine_km

    return haversine_km(cfg.location.latitude, cfg.location.longitude, store.lat, store.lon)


def fetch_offers(cfg: Config, chain: str = "mediamarkt") -> list[Offer]:
    url = cfg.url_for(chain)
    if not url:
        log.info("%s: keine Produkt-URL konfiguriert – übersprungen.", chain)
        return []

    online = _online_offers(cfg, chain, url)
    online_price = online[0].price if online else None
    store = _store_offers(cfg, chain, url, online_price)

    log.info("%s: %d online + %d Filial-Angebote.", chain, len(online), len(store))
    return online + store
