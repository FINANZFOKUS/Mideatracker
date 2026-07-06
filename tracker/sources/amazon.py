"""Amazon.de-Adapter inkl. Marketplace-Angebote ("Alle Angebote").

Amazon hat starken Anti-Bot-Schutz und kein verlässliches JSON-LD. Daher best
effort auf zwei Wegen:

1. **Angebotsliste** (``/gp/offer-listing/<ASIN>?aod=1``) – die belastbare
   Quelle: dort steht je Händler ein echtes Angebot mit Preis, Zustand und
   Warenkorb-Button. Nur ein Angebot MIT Warenkorb-Button gilt als bestellbar.
2. **Buybox** der Produktseite – nur als Ergänzung und bewusst STRENG: der Preis
   wird ausschließlich aus dem echten Buybox-Container gelesen (nie irgendein
   erstbester Preis der Seite), und "derzeit nicht verfügbar" ist ein Veto.
   So entstehen keine Phantom-Preise von Zubehör/Referenzpreisen.

Bei Block greift der Browser-Fallback; gelingt nichts, liefert der Adapter eine
leere Liste, ohne den Gesamtlauf zu stören.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ..config import Config, Product
from ..models import CHANNEL_ONLINE, CONDITION_NEW, CONDITION_USED, Offer
from .base import fetch_page, parse_price

log = logging.getLogger(__name__)

SOURCE = "amazon"

_ASIN_RE = re.compile(r"/(?:dp|gp/product|gp/offer-listing)/([A-Z0-9]{10})")

# Buybox: nur echte Buybox-Preis-Container – niemals ein beliebiges .a-offscreen
# der Seite (das wäre oft Zubehör oder ein durchgestrichener Referenzpreis).
_BUYBOX_PRICE_SELECTORS = (
    "#corePrice_feature_div .a-offscreen",
    "#corePriceDisplay_desktop_feature_div .a-offscreen",
    "#price_inside_buybox",
    "#newBuyBoxPrice",
    "#priceblock_ourprice",
)

# "Nicht bestellbar"-Marker: ein Veto für die Buybox.
_NEGATIVE_MARKERS = (
    "derzeit nicht verfügbar",
    "currently unavailable",
    "nicht auf lager",
    "vorübergehend nicht",
)

# Cart-Button in einer Angebotszeile / auf der Produktseite = tatsächlich bestellbar.
_CART_SELECTOR = "input[name='submit.addToCart'], input[name='submit.add-to-cart']"


def _asin(url: str) -> str | None:
    m = _ASIN_RE.search(url)
    return m.group(1) if m else None


def _classify_condition(heading: str) -> str:
    """Ordnet den Amazon-Zustandstext in neu/gebraucht ein.

    "Neu" => neu. Alles andere ("Gebraucht - …", "Sammlerstück - …",
    "Generalüberholt") gilt als gebraucht.
    """
    text = heading.lower()
    if "neu" in text and not any(
        w in text for w in ("gebraucht", "sammler", "generalüberholt", "wie neu")
    ):
        return CONDITION_NEW
    return CONDITION_USED


def _row_price(row) -> float | None:
    """Liest den Preis einer Angebotszeile – auch wenn Amazon ihn in
    ``a-price-whole`` + ``a-price-fraction`` zerlegt (``a-offscreen`` ist dort
    oft leer)."""
    off = row.select_one(".a-offscreen")
    if off and off.get_text(strip=True):
        price = parse_price(off.get_text(strip=True))
        if price is not None:
            return price
    whole = row.select_one(".a-price-whole")
    if whole:
        frac = row.select_one(".a-price-fraction")
        whole_text = whole.get_text(strip=True)
        if not whole_text.endswith((",", ".")):
            whole_text += ","
        return parse_price(whole_text + (frac.get_text(strip=True) if frac else "00"))
    return None


def _seller(row) -> str:
    el = row.select_one("#aod-offer-soldBy a.a-link-normal, #aod-offer-soldBy .a-size-small")
    name = el.get_text(strip=True) if el else ""
    return name[:40] if name else "Marketplace"


def parse_offer_listing(product: Product, html: str, asin: str) -> list[Offer]:
    """Parst die "Alle Angebote"-Seite in normalisierte Offer-Objekte."""
    soup = BeautifulSoup(html, "html.parser")
    dp_url = f"https://www.amazon.de/dp/{asin}"
    offers: list[Offer] = []
    for row in soup.select("#aod-pinned-offer, #aod-offer"):
        price = _row_price(row)
        if price is None:
            continue
        heading_el = row.select_one("#aod-offer-heading, [id*='condition']")
        heading = heading_el.get_text(" ", strip=True) if heading_el else "Neu"
        condition = _classify_condition(heading)
        in_stock = bool(row.select_one(_CART_SELECTOR))
        offers.append(
            Offer(
                source=SOURCE,
                title=product.name,
                price=price,
                url=dp_url,
                in_stock=in_stock,
                condition=condition,
                channel=CHANNEL_ONLINE,
                ean=product.eans[0] if product.eans else None,
                merchant=f"Amazon Marketplace ({_seller(row)})",
            )
        )
    return offers


def parse_buybox(product: Product, html: str, url: str) -> list[Offer]:
    """Streng: liest den Buybox-Preis NUR aus echten Buybox-Containern und
    vetoiert bei "nicht verfügbar". Kein Warenkorb-/Kaufen-Button => nicht
    bestellbar (kein Phantom-Preis)."""
    soup = BeautifulSoup(html, "html.parser")

    price = None
    for sel in _BUYBOX_PRICE_SELECTORS:
        el = soup.select_one(sel)
        if el:
            price = parse_price(el.get_text(strip=True))
            if price:
                break
    if price is None:
        return []  # keine echte Buybox => Amazon verkauft es aktuell nicht

    title_el = soup.select_one("#productTitle")
    title = title_el.get_text(strip=True) if title_el else product.name

    avail_el = soup.select_one("#availability")
    avail_text = avail_el.get_text(" ", strip=True).lower() if avail_el else ""
    page_text = soup.get_text(" ", strip=True).lower()
    if any(m in avail_text or m in page_text for m in _NEGATIVE_MARKERS):
        in_stock = False
    else:
        in_stock = bool(soup.select_one("#add-to-cart-button, #buy-now-button"))

    return [
        Offer(
            source=SOURCE,
            title=title,
            price=price,
            url=url,
            in_stock=in_stock,
            condition=CONDITION_NEW,
            channel=CHANNEL_ONLINE,
            ean=product.eans[0] if product.eans else None,
            merchant="Amazon.de",
        )
    ]


def _cheapest_per_condition(offers: list[Offer]) -> list[Offer]:
    """Reduziert viele identische Marketplace-Zeilen auf das jeweils günstigste
    bestellbare Angebot je Zustand (hält das Signal sauber)."""
    best: dict[str, Offer] = {}
    for o in offers:
        cur = best.get(o.condition)
        # bestellbare bevorzugen, dann günstigste
        better = (
            cur is None
            or (o.in_stock and not cur.in_stock)
            or (o.in_stock == cur.in_stock and o.price < cur.price)
        )
        if better:
            best[o.condition] = o
    return list(best.values())


def fetch_offers(cfg: Config, product: Product) -> list[Offer]:
    url = product.url_for(SOURCE)
    if not url:
        log.info("Amazon: keine Produkt-URL für '%s' konfiguriert – übersprungen.", product.name)
        return []

    asin = _asin(url)
    offers: list[Offer] = []

    # 1) Buybox der Produktseite (streng).
    html, how = fetch_page(url, wait_selector="#productTitle")
    if how == "blocked":
        log.info("Amazon: Produktseite – Bot-Wall/Captcha nicht überwunden (geblockt).")
    elif html:
        offers.extend(parse_buybox(product, html, url))

    # 2) Angebotsliste "Alle Angebote" (die belastbare Quelle).
    if asin:
        listing_url = f"https://www.amazon.de/gp/offer-listing/{asin}?aod=1"
        html, how = fetch_page(listing_url, wait_selector="#aod-offer-list")
        if how == "blocked":
            log.info("Amazon: Angebotsliste – Bot-Wall/Captcha nicht überwunden (geblockt).")
        elif html:
            offers.extend(_cheapest_per_condition(parse_offer_listing(product, html, asin)))

    # Über alle Quellen hinweg je Zustand nur das günstigste bestellbare Angebot.
    result = _cheapest_per_condition(offers)
    log.info("Amazon: %d Angebot(e) extrahiert.", len(result))
    return result
