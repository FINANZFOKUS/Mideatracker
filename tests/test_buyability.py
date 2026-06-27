"""Tests für strikte Kaufbarkeit + InStoreOnly-Behandlung (Anti-Pseudo)."""

from tracker.sources.buyability import assess_buyability
from tracker.sources.jsonld import extract_products

OBI_INSTOREONLY = """
<script type="application/ld+json">
{"@type":"Product","name":"Midea PortaSplit","gtin13":"4048164116478",
 "offers":{"@type":"Offer","price":"799.99","priceCurrency":"EUR",
 "availability":"http://schema.org/InStoreOnly"}}
</script>
<body><button id="add-to-cart-button">In den Warenkorb</button>
Verfügbarkeit im Markt prüfen</body>
"""

INSTOCK_ONLINE = """
<script type="application/ld+json">
{"@type":"Product","name":"Midea PortaSplit","gtin13":"4048164116478",
 "offers":{"@type":"Offer","price":"699.00","priceCurrency":"EUR",
 "availability":"https://schema.org/InStock"}}
</script>
<body><button id="add-to-cart-button">In den Warenkorb</button></body>
"""

INSTOCK_BUT_SOLD_OUT = """
<script type="application/ld+json">
{"@type":"Product","name":"Midea PortaSplit",
 "offers":{"@type":"Offer","price":"699.00","availability":"InStock"}}
</script>
<body>Dieser Artikel ist leider ausverkauft</body>
"""


def test_instoreonly_not_in_stock():
    # Der konkrete OBI-Pseudo-Fall: InStoreOnly darf NICHT als lieferbar gelten.
    p = extract_products(OBI_INSTOREONLY)[0]
    assert p["price"] == 799.99
    assert p["in_stock"] is False
    buyable, _ = assess_buyability(OBI_INSTOREONLY, jsonld_in_stock=p["in_stock"])
    assert buyable is False


def test_real_instock_is_buyable():
    p = extract_products(INSTOCK_ONLINE)[0]
    assert p["in_stock"] is True
    buyable, _ = assess_buyability(INSTOCK_ONLINE, jsonld_in_stock=p["in_stock"])
    assert buyable is True


def test_negative_marker_vetoes_instock():
    p = extract_products(INSTOCK_BUT_SOLD_OUT)[0]
    buyable, signals = assess_buyability(INSTOCK_BUT_SOLD_OUT, jsonld_in_stock=p["in_stock"])
    assert buyable is False
    assert "ausverkauft" in signals["negative_markers"]


def test_generic_markers_alone_not_enough():
    # Warenkorb-Button + "in den warenkorb" OHNE strukturiertes InStock
    # darf KEINEN Treffer erzeugen (Seiten-Chrome ist kein Beweis).
    html = '<body><button id="add-to-cart-button">In den Warenkorb</button></body>'
    buyable, _ = assess_buyability(html, jsonld_in_stock=False)
    assert buyable is False
