"""Parse and normalize .env files."""

from pathlib import Path
from typing import Dict
from dotenv import dotenv_values


class DotEnvIO:
    """Handle .env file I/O with normalization."""

    def parse(self, filepath: Path) -> Dict[str, str]:
        """Parse .env file to dictionary."""
        try:
            if not filepath.exists():
                raise FileNotFoundError(f"Environment file not found: {filepath}")
            return dict(dotenv_values(filepath))
        except FileNotFoundError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to parse {filepath}: {e}")

    def normalize(self, filepath: Path) -> str:
        """Parse and normalize .env file content."""
        data = self.parse(filepath)
        return self._dict_to_dotenv(data)

    def write(self, filepath: Path, data: Dict[str, str]) -> None:
        """Write normalized .env file."""
        try:
            content = self._dict_to_dotenv(data)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
        except OSError as e:
            raise OSError(f"Failed to write to {filepath}: {e}")

    def _dict_to_dotenv(self, data: Dict[str, str]) -> str:
        """Convert dictionary to normalized dotenv format."""
        lines = []

        # Sort keys alphabetically
        for key in sorted(data.keys()):
            value = data[key] or ""  # Handle None values

            # Add quotes if value contains spaces or special characters
            if self._needs_quotes(value):
                # Escape existing quotes
                value = value.replace('"', '\\"')
                value = f'"{value}"'

            lines.append(f"{key}={value}")

        return "\n".join(lines) + "\n"

    def _needs_quotes(self, value: str) -> bool:
        """Check if value needs quotes."""
        if not value:
            return False

        # Need quotes if contains spaces, equals, or other special chars
        special_chars = [' ', '=', '#', '\n', '\t']
        return any(char in value for char in special_chars)
