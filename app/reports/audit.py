import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


class AuditLog:
    """Local append-only-by-application JSONL, not tamper-proof storage."""
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = Lock()

    def append(self, event: str, **details):
        row = {"at": datetime.now(timezone.utc).isoformat(), "event": event, **details}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

