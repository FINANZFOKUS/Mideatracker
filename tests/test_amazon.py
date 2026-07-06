"""Tests für den Amazon-Adapter: Angebotsliste + strenge Buybox."""

from __future__ import annotations

from tracker.config import Product
from tracker.models import CONDITION_NEW, CONDITION_USED
from tracker.sources import amazon

PRODUCT = Product(
    name="Midea PortaSplit 12.000 BTU",
    eans=["4048164116478"],
    title_must_include=["portasplit"],
    title_must_exclude=[],
    max_price=1000.0,
    allow_used=True,
    urls={"amazon": "https://www.amazon.de/dp/B0D3PP64JS"},
)

ASIN = "B0D3PP64JS"


def _offer_row(*, whole: str, frac: str, heading: str, cart: bool, offscreen: str = "") -> str:
    cart_html = '<input name="submit.addToCart">' if cart else ""
    return f"""
    <div id="aod-offer">
      <span class="a-price">
        <span class="a-offscreen">{offscreen}</span>
        <span class="a-price-whole">{whole}</span><span class="a-price-fraction">{frac}</span>
      </span>
      <div id="aod-offer-heading"><span>{heading}</span></div>
      <div id="aod-offer-soldBy"><a class="a-link-normal">CoolShop</a></div>
      {cart_html}
    </div>
    """


def test_offer_listing_new_offer_under_budget_is_buyable():
    html = f"<div id='aod-offer-list'>{_offer_row(whole='769,', frac='00', heading='Neu', cart=True)}</div>"
    offers = amazon.parse_offer_listing(PRODUCT, html, ASIN)
    assert len(offers) == 1
    o = offers[0]
    assert o.price == 769.0
    assert o.condition == CONDITION_NEW
    assert o.in_stock is True
    assert o.ean == "4048164116478"


def test_offer_listing_parses_split_price_without_offscreen():
    # a-offscreen leer -> Preis muss aus whole+fraction kommen (2.919,00).
    html = f"<div id='aod-offer-list'>{_offer_row(whole='2.919,', frac='00', heading='Sammlerstück - Wie neu', cart=True)}</div>"
    offers = amazon.parse_offer_listing(PRODUCT, html, ASIN)
    assert offers[0].price == 2919.0
    assert offers[0].condition == CONDITION_USED  # Sammlerstück zählt als gebraucht


def test_offer_listing_no_cart_button_not_in_stock():
    html = f"<div id='aod-offer-list'>{_offer_row(whole='799,', frac='00', heading='Neu', cart=False)}</div>"
    offers = amazon.parse_offer_listing(PRODUCT, html, ASIN)
    assert offers[0].in_stock is False


def test_buybox_ignores_phantom_price_when_no_buybox_container():
    # Preis existiert nur irgendwo auf der Seite (Zubehör), NICHT in der Buybox.
    html = """
    <html><body>
      <span id="productTitle">Midea PortaSplit</span>
      <div id="some-accessory"><span class="a-price"><span class="a-offscreen">769,00 €</span></span></div>
    </body></html>
    """
    offers = amazon.parse_buybox(PRODUCT, html, PRODUCT.urls["amazon"])
    assert offers == []  # kein Phantom-Preis


def test_buybox_negative_marker_vetoes_stock():
    html = """
    <html><body>
      <span id="productTitle">Midea PortaSplit</span>
      <div id="corePrice_feature_div"><span class="a-offscreen">899,00 €</span></div>
      <div id="availability">Derzeit nicht verfügbar.</div>
      <input id="add-to-cart-button">
    </body></html>
    """
    offers = amazon.parse_buybox(PRODUCT, html, PRODUCT.urls["amazon"])
    assert len(offers) == 1
    assert offers[0].price == 899.0
    assert offers[0].in_stock is False  # trotz Preis + Button: "nicht verfügbar"


def test_buybox_available_with_cart_is_in_stock():
    html = """
    <html><body>
      <span id="productTitle">Midea PortaSplit</span>
      <div id="corePrice_feature_div"><span class="a-offscreen">780,00 €</span></div>
      <div id="availability">Auf Lager.</div>
      <input id="add-to-cart-button">
    </body></html>
    """
    offers = amazon.parse_buybox(PRODUCT, html, PRODUCT.urls["amazon"])
    assert offers[0].price == 780.0
    assert offers[0].in_stock is True
