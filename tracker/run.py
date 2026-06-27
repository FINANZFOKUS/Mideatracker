"""Einstiegspunkt: Quellen abfragen, filtern, Diff bilden, benachrichtigen.

Aufruf:
    python -m tracker.run            # echter Lauf (sendet Push, schreibt State)
    python -m tracker.run --dry-run  # nur loggen, kein Versand, kein State-Write
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import Config, Secrets, load_config
from .matching import is_buyable
from .models import CHANNEL_ONLINE, CONDITION_NEW, Offer
from .notify import format_offers, send_telegram
from .sources import get_source
from .state import diff_new, load_seen, save_seen

log = logging.getLogger(__name__)


def collect_offers(cfg: Config) -> list[Offer]:
    """Fragt alle aktivierten Quellen ab. Fehler isolieren pro Quelle."""
    all_offers: list[Offer] = []
    for name in cfg.enabled_sources():
        fn = get_source(name)
        if fn is None:
            log.warning("Unbekannte Quelle '%s' – übersprungen.", name)
            continue
        try:
            offers = fn(cfg)
            all_offers.extend(offers)
        except Exception as exc:  # noqa: BLE001 - eine Quelle darf nicht den Lauf kippen
            log.error("Quelle '%s' fehlgeschlagen: %s", name, exc, exc_info=True)
    return all_offers


def filter_buyable(cfg: Config, offers: list[Offer]) -> list[Offer]:
    return [o for o in offers if is_buyable(o, cfg)]


def run(dry_run: bool = False) -> int:
    cfg = load_config()
    secrets = Secrets.from_env()

    log.info("Starte Check für '%s' (max %.0f €, Quellen: %s)",
             cfg.product.name, cfg.product.max_price, ", ".join(cfg.enabled_sources()))

    offers = collect_offers(cfg)
    buyable = filter_buyable(cfg, offers)
    log.info("%d Angebote gesamt, davon %d wirklich bestellbar < %.0f €.",
             len(offers), len(buyable), cfg.product.max_price)
    for o in buyable:
        log.info("  ✓ %s", o.describe())

    seen = load_seen()
    new_offers, current_keys = diff_new(buyable, seen)

    if new_offers:
        log.info("%d NEUE verfügbare Angebote -> Benachrichtigung.", len(new_offers))
        message = format_offers(cfg.product.name, new_offers)
        if dry_run:
            print("--- DRY RUN: Telegram-Nachricht ---")
            print(message)
        else:
            send_telegram(message, secrets)
    else:
        log.info("Keine neuen verfügbaren Angebote.")

    if not dry_run:
        save_seen(current_keys)
        log.info("State aktualisiert (%d verfügbare Angebote gemerkt).", len(current_keys))

    return 0


def run_demo() -> int:
    """Schickt einen einmaligen Beispiel-Alarm im echten Format (Funktionstest)."""
    cfg = load_config()
    secrets = Secrets.from_env()
    demo = Offer(
        source="hornbach",
        title=f"{cfg.product.name} (BEISPIEL/Test)",
        price=699.0,
        url="https://www.hornbach.de/p/klimasplitgeraet-midea-portasplit-12-000-btu-105-m-weiss/12356554/",
        in_stock=True,
        condition=CONDITION_NEW,
        channel=CHANNEL_ONLINE,
        ean=cfg.product.eans[0] if cfg.product.eans else None,
        merchant="Hornbach (Test-Alarm)",
    )
    message = "🔔 <b>TEST-ALARM</b> – so sieht eine echte Benachrichtigung aus:\n\n" + format_offers(
        cfg.product.name, [demo]
    )
    ok = send_telegram(message, secrets)
    log.info("Test-Alarm gesendet." if ok else "Test-Alarm fehlgeschlagen (Secrets prüfen).")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Midea PortaSplit Verfügbarkeits-Check")
    parser.add_argument("--dry-run", action="store_true", help="Nur loggen, nichts senden/schreiben")
    parser.add_argument("--demo", action="store_true", help="Einmaligen Beispiel-Alarm an Telegram senden")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug-Logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    if args.demo:
        return run_demo()
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
