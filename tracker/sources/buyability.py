"""Strikte Kaufbarkeits-Erkennung anhand sichtbarer Seitensignale.

schema.org ``availability: InStock`` allein reicht NICHT – manche Shops (z.B.
OBI) melden das auch, wenn das Gerät gar nicht bestellbar ist ("Pseudo").
Daher kombinieren wir das strukturierte Signal mit positiven/negativen
Textmarkern und einem Warenkorb-/Lieferbutton.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Klar negative Signale → NICHT bestellbar (haben Vorrang).
NEGATIVE_MARKERS = (
    "nicht verfügbar",
    "nicht mehr verfügbar",
    "derzeit nicht verfügbar",
    "nicht lieferbar",
    "online nicht verfügbar",
    "online nicht bestellbar",
    "nicht bestellbar",
    "ausverkauft",
    "vergriffen",
    "out of stock",
    "sold out",
    "nur abholung",
    "nur im markt",
    "im markt verfügbar prüfen",
    "verfügbarkeit im markt",
    "benachrichtigen sie mich",
    "e-mail-benachrichtigung",
    "artikel ist aktuell nicht",
)

# Positive Signale → bestellbar.
POSITIVE_MARKERS = (
    "in den warenkorb",
    "in den einkaufswagen",
    "sofort lieferbar",
    "jetzt kaufen",
    "online bestellbar",
    "online verfügbar",
    "lieferung nach hause",
    "versandkostenfrei",
    "auf lager",
)

# Buttons/Selektoren, die echtes Bestellen erlauben.
ADD_TO_CART_SELECTORS = (
    "#add-to-cart-button",
    "button[name='submit.add-to-cart']",
    "[data-test*='add-to-cart']",
    "[data-testid*='add-to-cart']",
    "[class*='add-to-cart']",
    "[class*='addToCart']",
    "[class*='basket']",
    "button[class*='warenkorb']",
)


def assess_buyability(html: str, *, jsonld_in_stock: bool) -> tuple[bool, dict]:
    """Bewertet, ob ein Artikel WIRKLICH bestellbar ist.

    Logik:
      * Negativer Marker im Text  → nicht bestellbar (stärkstes Signal).
      * Sonst bestellbar, wenn Warenkorb-Button ODER positiver Marker ODER
        (strukturiertes InStock UND kein gegenteiliges Signal).
    Returns (buyable, signals) – signals dient der Diagnose.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True).lower()
    text = re.sub(r"\s+", " ", text)

    found_negative = [m for m in NEGATIVE_MARKERS if m in text]
    found_positive = [m for m in POSITIVE_MARKERS if m in text]
    has_cart = any(soup.select(sel) for sel in ADD_TO_CART_SELECTORS)

    if found_negative:
        buyable = False
    elif has_cart or found_positive:
        buyable = True
    else:
        # Kein eindeutiges Seitensignal: nur dem strukturierten InStock trauen,
        # wenn es vorhanden ist – sonst konservativ ablehnen.
        buyable = bool(jsonld_in_stock)

    signals = {
        "jsonld_in_stock": jsonld_in_stock,
        "has_cart_button": has_cart,
        "positive_markers": found_positive,
        "negative_markers": found_negative,
    }
    return buyable, signals
