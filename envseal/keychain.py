"""Local macOS Keychain backend for persistent developer secrets.

Secret values are never accepted as command-line arguments.  ``security``
prompts for writes and only returns a value to the broker when it must inject
that value into a child process.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass

DEFAULT_SERVICE = "com.chicogong.envseal"


class KeychainError(RuntimeError):
    """A safe, value-free Keychain operation error."""


@dataclass
class KeychainStore:
    """Store references as Generic Password items in the login Keychain."""

    service: str = DEFAULT_SERVICE

    def available(self) -> bool:
        """Return whether the macOS ``security`` client is available."""
        return platform.system() == "Darwin" and shutil.which("security") is not None

    def put_interactive(self, reference: str) -> None:
        """Prompt securely and add or update a secret.

        Passing ``-w`` as the final flag makes macOS prompt rather than placing
        the secret in argv, shell history, or EnvSeal's own input buffers.
        """
        self._require_available()
        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-a",
                reference,
                "-s",
                self.service,
                "-l",
                f"EnvSeal: {reference}",
                # Do not automatically trust the creating ``security`` tool.
                # macOS will mediate later reads instead of silently granting
                # every same-user process that can invoke that executable.
                "-T",
                "",
                "-w",
            ],
            check=False,
        )
        if result.returncode != 0:
            raise KeychainError("Keychain write was cancelled or failed")

    def get(self, reference: str) -> str:
        """Read a value for immediate injection into a trusted child process."""
        self._require_available()
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                reference,
                "-s",
                self.service,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise KeychainError(f"Secret reference not found in Keychain: {reference}")
        return result.stdout.rstrip("\n")

    def contains(self, reference: str) -> bool:
        """Check item presence without requesting or returning its value."""
        self._require_available()
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                reference,
                "-s",
                self.service,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    def delete(self, reference: str) -> None:
        """Delete a referenced item without ever reading its value."""
        self._require_available()
        result = subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-a",
                reference,
                "-s",
                self.service,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise KeychainError(f"Secret reference not found in Keychain: {reference}")

    def _require_available(self) -> None:
        if not self.available():
            raise KeychainError("The Keychain backend is available only on macOS")
