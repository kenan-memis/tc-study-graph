from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ResponseCache:
    def __init__(self, base_dir: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        memory_dir = base_dir or (root / "data" / "memory")
        memory_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = memory_dir / "response_cache.json"

    @staticmethod
    def _key(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _read_all(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return {}
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}

    def _write_all(self, data: dict[str, Any]) -> None:
        self.cache_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        data = self._read_all()
        key = self._key(payload)
        value = data.get(key)
        return value if isinstance(value, dict) else None

    def set(self, payload: dict[str, Any], value: dict[str, Any]) -> None:
        data = self._read_all()
        key = self._key(payload)
        data[key] = value
        self._write_all(data)
