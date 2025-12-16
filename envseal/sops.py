"""SOPS encryption wrapper for dotenv files."""

import os
import subprocess
from pathlib import Path
from typing import Optional


class SopsManager:
    """Manage SOPS encryption/decryption operations."""

    def __init__(self, age_public_key: str, age_key_file: Optional[Path] = None):
        self.age_public_key = age_public_key
        self.age_key_file = age_key_file

    def encrypt(self, input_file: Path, output_file: Path) -> None:
        """Encrypt a dotenv file using SOPS."""
        env = os.environ.copy()
        env["SOPS_AGE_RECIPIENTS"] = self.age_public_key

        if self.age_key_file:
            env["SOPS_AGE_KEY_FILE"] = str(self.age_key_file)

        result = subprocess.run(
            [
                "sops",
                "--encrypt",
                "--input-type",
                "dotenv",
                "--output-type",
                "dotenv",
                "--output",
                str(output_file),
                str(input_file),
            ],
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"SOPS encryption failed: {result.stderr}")

    def decrypt(self, encrypted_file: Path) -> str:
        """Decrypt a SOPS-encrypted dotenv file."""
        env = os.environ.copy()

        if self.age_key_file:
            env["SOPS_AGE_KEY_FILE"] = str(self.age_key_file)

        result = subprocess.run(
            [
                "sops",
                "--decrypt",
                "--input-type",
                "dotenv",
                "--output-type",
                "dotenv",
                str(encrypted_file),
            ],
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"SOPS decryption failed: {result.stderr}")

        return result.stdout

    def create_sops_yaml(self, output_path: Path) -> None:
        """Create .sops.yaml configuration file."""
        content = f"""creation_rules:
  - path_regex: ^secrets/.*\\.env$
    input_type: dotenv
    age: {self.age_public_key}
"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
