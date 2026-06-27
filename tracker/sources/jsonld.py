"""Extraktion von Produkt-/Angebotsdaten aus schema.org JSON-LD.

Die meisten deutschen Shops (OBI, Bauhaus, Hornbach, MediaMarkt, Saturn,
Amazon) betten strukturierte Daten als ``<script type="application/ld+json">``
ein. Das ist der stabilste, shop-übergreifende Vertrag und damit unsere
bevorzugte Parsing-Strategie. Selektor-basiertes HTML-Parsing dient nur als
Fallback in den einzelnen Adaptern.
"""

from __future__ import annotations

import json
import logging

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# schema.org availability-Werte, die "kaufbar" bedeuten.
_IN_STOCK_TOKENS = {
    "instock",
    "in_stock",
    "limitedavailability",
    "onlineonly",
    "instoreonly",
    "presale",
}


def _iter_nodes(data) -> list[dict]:
    """Flacht verschachtelte JSON-LD-Strukturen (@graph, Listen) zu dicts ab."""
    nodes: list[dict] = []
    stack = [data]
    while stack:
        cur = stack.pop()
        if isinstance(cur, list):
            stack.extend(cur)
        elif isinstance(cur, dict):
            nodes.append(cur)
            if "@graph" in cur:
                stack.append(cur["@graph"])
    return nodes


def _availability_in_stock(value) -> bool:
    if not value:
        return False
    if isinstance(value, list):
        return any(_availability_in_stock(v) for v in value)
    token = str(value).rsplit("/", 1)[-1].strip().lower().replace("-", "")
    return token in _IN_STOCK_TOKENS


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _gtin_from(node: dict) -> str | None:
    for key in ("gtin13", "gtin", "gtin14", "gtin12", "gtin8", "ean"):
        if node.get(key):
            return str(node[key]).strip()
    return None


def extract_products(html: str) -> list[dict]:
    """Gibt eine Liste normalisierter Produkt-Angebote zurück.

    Jeder Eintrag: ``{title, ean, price, currency, in_stock}``. Es werden alle
    ``Product``-Knoten mit mindestens einem ``offers``-Eintrag berücksichtigt.
    """
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Manche Shops packen mehrere JSON-Objekte / kaputtes JSON hinein.
            continue

        for node in _iter_nodes(data):
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if not any(t and "product" in str(t).lower() for t in types):
                continue

            title = node.get("name") or ""
            ean = _gtin_from(node)
            offers = node.get("offers")
            if offers is None:
                continue
            offer_nodes = offers if isinstance(offers, list) else [offers]

            for off in offer_nodes:
                if not isinstance(off, dict):
                    continue
                # AggregateOffer: tiefster Preis ist am relevantesten.
                spec = off.get("priceSpecification")
                spec_price = spec.get("price") if isinstance(spec, dict) else None
                price = _to_float(
                    off.get("price") or off.get("lowPrice") or spec_price
                )
                results.append(
                    {
                        "title": title,
                        "ean": ean,
                        "price": price,
                        "currency": off.get("priceCurrency") or "EUR",
                        "in_stock": _availability_in_stock(off.get("availability")),
                        "availability_raw": off.get("availability"),
                    }
                )

    return results
