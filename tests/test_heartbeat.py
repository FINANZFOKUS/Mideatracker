"""Tests für Heartbeat + Totalausfall-Alarm (Entprellung 1x/Tag)."""

from datetime import datetime, timezone

from tracker import run as run_mod
from tracker.config import Config, Location, Product
from tracker.notify import format_heartbeat, format_outage
from tracker.run import RunSummary, _maybe_heartbeat


def _cfg(heartbeat_enabled=True, hour=6) -> Config:
    return Config(
        products=[Product("Gerät", ["111"], ["x"], [], 800.0, False)],
        location=Location("74321", "BB", 48.95, 9.13, 25.0),
        sources={},
        stores={},
        heartbeat_enabled=heartbeat_enabled,
        heartbeat_hour_utc=hour,
    )


class _Sender:
    """Mock für send_telegram: zählt Aufrufe, gibt konfigurierten Erfolg zurück."""

    def __init__(self, ok=True):
        self.ok = ok
        self.messages = []

    def __call__(self, text, secrets):
        self.messages.append(text)
        return self.ok


def _summary(attempts=8, with_data=2, buyable=0, best=True) -> RunSummary:
    s = RunSummary(attempts=attempts, sources_with_data=with_data, buyable_count=buyable)
    if best:
        s.note_best("Gerät", 1799.0, "Geizhals")
    return s


AT7 = datetime(2026, 6, 30, 7, 0, tzinfo=timezone.utc)
AT5 = datetime(2026, 6, 30, 5, 0, tzinfo=timezone.utc)


def test_heartbeat_sends_once_per_day(monkeypatch):
    sender = _Sender(ok=True)
    monkeypatch.setattr(run_mod, "send_telegram", sender)
    monkeypatch.setattr(run_mod, "datetime", _fixed_now(AT7))
    state = {}

    _maybe_heartbeat(_cfg(), state, _summary(), None, dry_run=False)
    assert len(sender.messages) == 1
    assert state["last_heartbeat"] == "2026-06-30"

    # Zweiter Lauf am selben Tag -> kein erneuter Versand.
    _maybe_heartbeat(_cfg(), state, _summary(), None, dry_run=False)
    assert len(sender.messages) == 1


def test_heartbeat_waits_for_hour(monkeypatch):
    sender = _Sender(ok=True)
    monkeypatch.setattr(run_mod, "send_telegram", sender)
    monkeypatch.setattr(run_mod, "datetime", _fixed_now(AT5))  # vor 06 UTC
    state = {}
    _maybe_heartbeat(_cfg(hour=6), state, _summary(), None, dry_run=False)
    assert sender.messages == []
    assert "last_heartbeat" not in state


def test_heartbeat_disabled(monkeypatch):
    sender = _Sender(ok=True)
    monkeypatch.setattr(run_mod, "send_telegram", sender)
    monkeypatch.setattr(run_mod, "datetime", _fixed_now(AT7))
    _maybe_heartbeat(_cfg(heartbeat_enabled=False), {}, _summary(), None, dry_run=False)
    assert sender.messages == []


def test_total_outage_alerts_once(monkeypatch):
    sender = _Sender(ok=True)
    monkeypatch.setattr(run_mod, "send_telegram", sender)
    monkeypatch.setattr(run_mod, "datetime", _fixed_now(AT7))
    state = {}
    out = _summary(attempts=8, with_data=0, best=False)

    _maybe_heartbeat(_cfg(), state, out, None, dry_run=False)
    assert len(sender.messages) == 1
    assert "Totalausfall" in sender.messages[0]
    assert state["last_outage_alert"] == "2026-06-30"
    # Kein normaler Heartbeat bei Totalausfall.
    assert "last_heartbeat" not in state

    _maybe_heartbeat(_cfg(), state, out, None, dry_run=False)
    assert len(sender.messages) == 1  # nicht erneut


def test_no_outage_when_some_data(monkeypatch):
    sender = _Sender(ok=True)
    monkeypatch.setattr(run_mod, "send_telegram", sender)
    monkeypatch.setattr(run_mod, "datetime", _fixed_now(AT7))
    _maybe_heartbeat(_cfg(), {}, _summary(with_data=1), None, dry_run=False)
    assert "Totalausfall" not in (sender.messages[0] if sender.messages else "")


def test_format_heartbeat_escapes_and_lists_best():
    s = RunSummary(attempts=8, sources_with_data=2, buyable_count=0)
    s.note_best("Gerät & <X>", 749.0, "Shop <b>")
    msg = format_heartbeat(s, AT7)
    assert "Gerät &amp; &lt;X&gt;" in msg
    assert "749.00 €" in msg
    assert "2/8" in msg


def test_format_outage_mentions_attempts():
    assert "8 Abrufversuche" in format_outage(RunSummary(attempts=8))


def _fixed_now(dt):
    """Erzeugt einen datetime-Ersatz, dessen now(tz) immer dt liefert."""

    class _DT(datetime):
        @classmethod
        def now(cls, tz=None):
            return dt

    return _DT
