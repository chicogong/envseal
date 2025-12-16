"""Calculate diffs between .env files (key-only)."""

from dataclasses import dataclass, field
from io import StringIO

from dotenv import dotenv_values


@dataclass
class DiffResult:
    """Result of a diff calculation."""

    added: set[str] = field(default_factory=set)
    removed: set[str] = field(default_factory=set)
    modified: set[str] = field(default_factory=set)

    def is_clean(self) -> bool:
        """Check if there are no changes."""
        return len(self.added) == 0 and len(self.removed) == 0 and len(self.modified) == 0

    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return not self.is_clean()


class DiffCalculator:
    """Calculate key-only diffs between .env contents."""

    def calculate(self, old_content: str, new_content: str) -> DiffResult:
        """Calculate diff between two .env contents."""
        old_data = self._parse_content(old_content)
        new_data = self._parse_content(new_content)

        old_keys = set(old_data.keys())
        new_keys = set(new_data.keys())

        added = new_keys - old_keys
        removed = old_keys - new_keys

        # Check for modified values in common keys
        common_keys = old_keys & new_keys
        modified = {key for key in common_keys if old_data[key] != new_data[key]}

        return DiffResult(added=added, removed=removed, modified=modified)

    def _parse_content(self, content: str) -> dict[str, str]:
        """Parse .env content string to dictionary."""
        # Filter out None values to match return type
        return {k: v for k, v in dotenv_values(stream=StringIO(content)).items() if v is not None}
