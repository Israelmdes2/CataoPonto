"""
Gravador de macros (mouse + teclado).
Macro recorder (mouse + keyboard).

Uso / Use:
    rec = Recorder()
    rec.start()
    # ... ações manuais
    macro = rec.stop()
    Recorder.save(macro, "macro.json")
    later = Recorder.load("macro.json")
    Recorder.play(later, speed=1.5)
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Evento gravado (mouse_move, click, key, etc.)."""
    type: str
    ts:   float                       # timestamp relativo ao início
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Macro:
    events: list[Event] = field(default_factory=list)
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "duration_s": self.duration_s,
            "events": [asdict(e) for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Macro":
        return cls(
            duration_s=data.get("duration_s", 0.0),
            events=[Event(**e) for e in data.get("events", [])],
        )


class Recorder:
    """Gravador simples baseado em polling."""

    def __init__(self, poll_interval: float = 0.05):
        self.poll_interval = poll_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._macro = Macro()
        self._start_ts = 0.0

    # ── controle / control ────────────────────────────────────

    def start(self) -> None:
        from infrastructure.automation import gui
        gui._ensure_display()
        self._macro = Macro()
        self._stop_evt.clear()
        self._start_ts = time.time()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("[Recorder] gravando / recording...")

    def stop(self) -> Macro:
        self._stop_evt.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._macro.duration_s = time.time() - self._start_ts
        logger.info("[Recorder] %d eventos em %.1fs",
                    len(self._macro.events), self._macro.duration_s)
        return self._macro

    # ── loop ──────────────────────────────────────────────────

    def _loop(self) -> None:
        from infrastructure.automation import gui
        last_pos = None
        while not self._stop_evt.is_set():
            try:
                pos = gui.mouse_position()
                if pos != last_pos:
                    self._macro.events.append(Event(
                        type="mouse_move",
                        ts=time.time() - self._start_ts,
                        data={"x": pos[0], "y": pos[1]},
                    ))
                    last_pos = pos
            except Exception:
                pass
            time.sleep(self.poll_interval)

    # ── replay ────────────────────────────────────────────────

    @staticmethod
    def play(macro: Macro, speed: float = 1.0) -> None:
        """Reproduz o macro / Replay the macro."""
        from infrastructure.automation import gui
        gui._ensure_display()
        if speed <= 0:
            raise ValueError("speed deve ser > 0 / must be > 0")
        start = time.time()
        for ev in macro.events:
            target = ev.ts / speed
            wait   = target - (time.time() - start)
            if wait > 0:
                time.sleep(wait)
            _apply_event(ev, gui)

    # ── serialização / serialization ──────────────────────────

    @staticmethod
    def save(macro: Macro, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(macro.to_dict(), indent=2), encoding="utf-8")

    @staticmethod
    def load(path: Union[str, Path]) -> Macro:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return Macro.from_dict(data)


def _apply_event(ev: Event, gui) -> None:
    if ev.type == "mouse_move":
        gui.move_to(ev.data["x"], ev.data["y"], duration=0)
    elif ev.type == "click":
        gui.click(ev.data["x"], ev.data["y"], button=ev.data.get("button", "left"))
    elif ev.type == "key":
        gui.press(ev.data["key"])
    elif ev.type == "type":
        gui.type_text(ev.data["text"])
