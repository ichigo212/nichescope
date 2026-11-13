"""Background jobs for long operations, with progress published as events.

One job runs at a time: map operations read and write the same files and share the
YouTube quota, so running them in parallel gains little and risks conflicts.
"""
from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from collections import deque
from collections.abc import Callable
from typing import Any

from ..research.storage import MapNotFound
from ..youtube.data_api import YouTubeError

log = logging.getLogger(__name__)

EVENTS_KEPT = 500
EXPECTED = (ValueError, LookupError, RuntimeError, YouTubeError, MapNotFound)


class Busy(RuntimeError):
    pass


class Jobs:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._seq = 0
        self._events: deque[dict] = deque(maxlen=EVENTS_KEPT)
        self.current: dict | None = None
        self.recent: deque[dict] = deque(maxlen=20)

    def publish(self, event: dict) -> None:
        with self._cond:
            self._seq += 1
            self._events.append({**event, "seq": self._seq})
            self._cond.notify_all()

    def wait(self, after: int, timeout: float) -> list[dict]:
        """Events newer than `after`, waiting up to `timeout` seconds for one."""
        with self._cond:
            if self._seq <= after:
                self._cond.wait(timeout)
            return [e for e in self._events if e["seq"] > after]

    @property
    def seq(self) -> int:
        return self._seq

    @property
    def busy(self) -> bool:
        return self.current is not None

    def start(self, kind: str, label: str, fn: Callable[[Callable[[str], None]], Any],
              map_id: str | None = None, on_done: Callable[[Any], dict | None] | None = None) -> dict:
        """Run `fn(report)` in the background. Raises Busy if another job is running."""
        with self._cond:
            if self.current is not None:
                raise Busy(f"wait for the current job to finish: {self.current['label']}")
            job = {"id": uuid.uuid4().hex[:12], "kind": kind, "label": label, "map_id": map_id,
                   "status": "running", "message": "", "started_at": time.time(), "error": None}
            self.current = job
        self.publish({"type": "job", "job": dict(job)})

        def report(text: str) -> None:
            job["message"] = str(text)[:300]
            self.publish({"type": "job", "job": dict(job)})

        def run() -> None:
            extra: dict = {}
            try:
                result = fn(report)
                job["status"] = "done"
                if on_done:
                    extra = on_done(result) or {}
            except EXPECTED as e:
                job["status"], job["error"] = "failed", str(e)
                log.warning("job %s failed: %s", label, e)
            except Exception as e:  # noqa: BLE001 - report every failure to the client
                job["status"], job["error"] = "failed", f"{type(e).__name__}: {e}"
                log.error("job %s crashed\n%s", label, traceback.format_exc())
            job["finished_at"] = time.time()
            with self._cond:
                self.current = None
                self.recent.appendleft(dict(job))
            self.publish({"type": "job", "job": dict(job), **extra})

        threading.Thread(target=run, name=f"job-{kind}", daemon=True).start()
        return dict(job)


jobs = Jobs()
