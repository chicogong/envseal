"""Cryptographic key management for age encryption."""

import os
import subprocess
from pathlib import Path
from typing import Optional


class AgeKeyManager:
    """Manage age encryption keys."""

    def get_default_key_path(self) -> Path:
        """Get the default age key path for SOPS."""
        if os.name == "posix":
            # macOS/Linux
            if os.uname().sysname == "Darwin":
                base = Path.home() / "Library" / "Application Support"
            else:
                base = Path.home() / ".config"
            return base / "sops" / "age" / "keys.txt"
        else:
            # Windows
            return Path.home() / "AppData" / "Local" / "sops" / "age" / "keys.txt"

    def generate_key(self, key_file: Path) -> str:
        """Generate a new age key pair and return public key."""
        # Ensure parent directory exists
        key_file.parent.mkdir(parents=True, exist_ok=True)

        # Generate key using age-keygen
        result = subprocess.run(
            ["age-keygen", "-o", str(key_file)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to generate age key: {result.stderr}")

        # Set file permissions to 600
        os.chmod(key_file, 0o600)

        # Extract public key from output
        # age-keygen outputs: "Public key: age1..."
        for line in result.stderr.split("\n"):
            if line.startswith("Public key:"):
                return line.split(":", 1)[1].strip()

        raise RuntimeError("Could not extract public key from age-keygen output")

    def get_public_key(self, key_file: Path) -> str:
        """Extract public key from existing key file."""
        if not key_file.exists():
            raise FileNotFoundError(f"Key file not found: {key_file}")

        # Read the key file and convert private key to public key
        result = subprocess.run(
            ["age-keygen", "-y", str(key_file)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to get public key: {result.stderr}")

        return result.stdout.strip()

    def key_exists(self, key_file: Optional[Path] = None) -> bool:
        """Check if age key exists."""
        if key_file is None:
            key_file = self.get_default_key_path()
        return key_file.exists()
