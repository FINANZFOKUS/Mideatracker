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
    """Bewertet KONSERVATIV, ob ein Artikel WIRKLICH online bestellbar ist.

    Grundsatz: Pseudo-Treffer um jeden Preis vermeiden. Generische Texte wie
    "in den Warenkorb" oder "versandkostenfrei" stehen auf JEDER Produktseite
    und sind daher KEIN Beweis. Vertraut wird nur dem strukturierten
    schema.org-Signal (InStock/OnlineOnly – NICHT InStoreOnly), und ein
    negativer Marker hebt das wieder auf.

    Logik:
      * Negativer Marker ("ausverkauft", "nicht verfügbar", "nur im Markt" …)
        → nicht bestellbar (Veto, stärkstes Signal).
      * Sonst bestellbar genau dann, wenn das strukturierte InStock-Signal da ist.
      * Generische positive Marker / Warenkorb-Button dienen nur der Diagnose.
    Returns (buyable, signals).
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True).lower()
    text = re.sub(r"\s+", " ", text)

    found_negative = [m for m in NEGATIVE_MARKERS if m in text]
    found_positive = [m for m in POSITIVE_MARKERS if m in text]
    has_cart = any(soup.select(sel) for sel in ADD_TO_CART_SELECTORS)

    buyable = bool(jsonld_in_stock) and not found_negative

    signals = {
        "jsonld_in_stock": jsonld_in_stock,
        "has_cart_button": has_cart,
        "positive_markers": found_positive,
        "negative_markers": found_negative,
    }
    return buyable, signals
