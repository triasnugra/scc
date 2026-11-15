"""State JSON sederhana (atomic write) - dipersist antar run (Actions branch `data` / volume Docker)."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DEFAULT = {
    "day": "", "day_start_equity": None, "equity": None,
    "open": [], "closed": [], "seen": [], "signals": [],
    "trades_today": [], "consecutive_losses": 0, "last_loss_ts": None, "halted_reason": "",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class State:
    def __init__(self, path: str = "state/state.json"):
        self.path = Path(path)
        self.d = json.loads(json.dumps(DEFAULT))
        if self.path.exists():
            self.d.update(json.loads(self.path.read_text()))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.d["seen"] = self.d["seen"][-500:]
        self.d["signals"] = self.d["signals"][-100:]
        self.d["closed"] = self.d["closed"][-300:]
        fd, tmp = tempfile.mkstemp(dir=self.path.parent)
        with os.fdopen(fd, "w") as f:
            json.dump(self.d, f, indent=1, default=str)
        os.replace(tmp, self.path)

    def roll_day(self, equity: float) -> None:
        today = utcnow().strftime("%Y-%m-%d")
        if self.d["day"] != today:
            self.d.update(day=today, day_start_equity=equity, trades_today=[], halted_reason="", consecutive_losses=0)
        self.d["equity"] = equity
