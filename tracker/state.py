"""Persistenter Zustand zwischen den Läufen + Diff-Logik (Anti-Spam)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from .config import ROOT
from .models import Offer

STATE_PATH = ROOT / "state.json"


def load_state(path: Path = STATE_PATH) -> dict:
    """Lädt den kompletten Zustand (Keys + Meta wie Heartbeat-Datum)."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def load_seen(path: Path = STATE_PATH) -> set[str]:
    """Lädt die Menge der beim letzten Lauf verfügbaren Angebots-Schlüssel."""
    return set(load_state(path).get("available_keys", []))


def save_seen(keys: Iterable[str], path: Path = STATE_PATH) -> None:
    """Speichert die Keys und ERHÄLT dabei vorhandene Meta-Felder."""
    state = load_state(path)
    state["available_keys"] = sorted(set(keys))
    save_state(state, path)


def diff_new(available: list[Offer], seen: set[str]) -> tuple[list[Offer], set[str]]:
    """Ermittelt neu verfügbar gewordene Angebote.

    Returns:
        (new_offers, current_keys)
        - new_offers: Angebote, deren Schlüssel zuvor nicht "verfügbar" war.
        - current_keys: alle aktuell verfügbaren Schlüssel (= neuer State).
    """
    current_keys = {o.key() for o in available}
    new_offers = [o for o in available if o.key() not in seen]
    return new_offers, current_keys
