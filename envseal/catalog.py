"""Value-free local metadata catalog for secret references."""

from __future__ import annotations

import builtins
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class SecretMetadata:
    """Metadata safe for humans and AI assistants to inspect."""

    reference: str
    backend: str
    updated_at: str


class SecretCatalog:
    """Maintain a private catalog containing names, never values."""

    def __init__(self, path: Path | None = None):
        self.path = path or self.default_path()

    @staticmethod
    def default_path() -> Path:
        return Path.home() / ".local" / "share" / "envseal" / "catalog.json"

    def list(self) -> builtins.list[SecretMetadata]:
        data = self._load()
        try:
            return [SecretMetadata(**item) for item in data]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid EnvSeal catalog: {self.path}") from exc

    def record(self, reference: str, backend: str = "keychain") -> None:
        items = {item.reference: item for item in self.list()}
        items[reference] = SecretMetadata(
            reference=reference,
            backend=backend,
            updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._save(sorted(items.values(), key=lambda item: item.reference.lower()))

    def remove(self, reference: str) -> None:
        self._save([item for item in self.list() if item.reference != reference])

    def permissions_are_private(self) -> bool:
        file_private = not self.path.exists() or (self.path.stat().st_mode & 0o077) == 0
        parent_private = (
            not self.path.parent.exists() or (self.path.parent.stat().st_mode & 0o077) == 0
        )
        return file_private and parent_private

    def _load(self) -> builtins.list[dict[str, str]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid EnvSeal catalog: {self.path}") from exc
        required = {"reference", "backend", "updated_at"}
        if not isinstance(data, list) or not all(
            isinstance(item, dict)
            and set(item) == required
            and all(isinstance(value, str) for value in item.values())
            for item in data
        ):
            raise ValueError(f"Invalid EnvSeal catalog: {self.path}")
        return cast(builtins.list[dict[str, str]], data)

    def _save(self, items: builtins.list[SecretMetadata]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        payload = json.dumps([asdict(item) for item in items], indent=2) + "\n"
        fd, temp_name = tempfile.mkstemp(prefix="catalog-", dir=self.path.parent)
        temp_path = Path(temp_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            temp_path.replace(self.path)
            os.chmod(self.path, 0o600)
        finally:
            if temp_path.exists():
                temp_path.unlink()
