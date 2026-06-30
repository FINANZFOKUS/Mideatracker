"""Tests für das Laden der Config: neues Multi-Produkt- UND altes Format."""

from pathlib import Path

from tracker.config import load_config

NEW_FORMAT = """
products:
  - name: "Gerät A"
    eans: ["111"]
    title_must_include: ["a"]
    title_must_exclude: []
    max_price: 800
    allow_used: true
    urls:
      idealo: "https://idealo/a"
      obi: "https://obi/a"
  - name: "Gerät B"
    eans: ["222"]
    title_must_include: ["b"]
    title_must_exclude: ["alt"]
    max_price: 500
    allow_used: false
    urls:
      idealo: "https://idealo/b"

location:
  postal_code: "74321"
  city: "Bietigheim-Bissingen"
  latitude: 48.9543
  longitude: 9.1316
  radius_km: 25

sources:
  idealo: true
  obi: false
"""

LEGACY_FORMAT = """
product:
  name: "Altgerät"
  eans: ["999"]
  title_must_include: ["alt"]
  title_must_exclude: []
  max_price: 700
  allow_used: false

location:
  postal_code: "74321"
  city: "Bietigheim-Bissingen"
  latitude: 48.9543
  longitude: 9.1316
  radius_km: 25

sources:
  idealo: true

source_urls:
  idealo: "https://idealo/legacy"
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_loads_new_multi_product_format(tmp_path):
    cfg = load_config(_write(tmp_path, NEW_FORMAT), tmp_path / "stores.yaml")
    assert [p.name for p in cfg.products] == ["Gerät A", "Gerät B"]
    assert cfg.products[0].url_for("idealo") == "https://idealo/a"
    assert cfg.products[0].url_for("obi") == "https://obi/a"
    assert cfg.products[1].max_price == 500
    assert cfg.products[1].allow_used is False
    # Quellen-Schalter bleiben global.
    assert cfg.enabled_sources() == ["idealo"]


def test_loads_legacy_single_product_format(tmp_path):
    cfg = load_config(_write(tmp_path, LEGACY_FORMAT), tmp_path / "stores.yaml")
    assert len(cfg.products) == 1
    prod = cfg.product
    assert prod.name == "Altgerät"
    # Alte source_urls werden dem einzigen Produkt zugeordnet.
    assert prod.url_for("idealo") == "https://idealo/legacy"


def test_url_for_missing_source_is_empty(tmp_path):
    cfg = load_config(_write(tmp_path, NEW_FORMAT), tmp_path / "stores.yaml")
    assert cfg.products[1].url_for("amazon") == ""


def test_heartbeat_defaults_when_absent(tmp_path):
    cfg = load_config(_write(tmp_path, NEW_FORMAT), tmp_path / "stores.yaml")
    assert cfg.heartbeat_enabled is True
    assert cfg.heartbeat_hour_utc == 6


def test_heartbeat_override(tmp_path):
    text = NEW_FORMAT + "\nheartbeat:\n  enabled: false\n  hour_utc: 9\n"
    cfg = load_config(_write(tmp_path, text), tmp_path / "stores.yaml")
    assert cfg.heartbeat_enabled is False
    assert cfg.heartbeat_hour_utc == 9
