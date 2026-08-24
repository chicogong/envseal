"""Run trusted child processes with short-lived secret injection."""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Mapping, Sequence

from envseal.keychain import KeychainStore

ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_binding(binding: str) -> tuple[str, str]:
    """Parse ``ENV_NAME=secret/reference`` without touching a value."""
    if "=" not in binding:
        raise ValueError("Secret binding must use ENV_NAME=reference")
    name, reference = binding.split("=", 1)
    if not ENV_NAME.fullmatch(name):
        raise ValueError(f"Invalid environment variable name: {name}")
    validate_reference(reference)
    return name, reference


def validate_reference(reference: str) -> None:
    """Require a namespaced, relative reference safe for metadata and argv."""
    if not reference or reference.startswith("/") or reference.endswith("/"):
        raise ValueError("Secret reference must be a non-empty relative path")
    if any(part in {"", ".", ".."} for part in reference.split("/")):
        raise ValueError("Secret reference contains an unsafe path segment")
    if reference.startswith("-") or any(char in reference for char in "\n\r\x00"):
        raise ValueError("Secret reference contains unsafe characters")


class SecretBroker:
    """Resolve references just in time and inject them into one child process."""

    def __init__(self, keychain: KeychainStore | None = None):
        self.keychain = keychain or KeychainStore()

    def run(
        self,
        command: Sequence[str],
        bindings: Sequence[str],
        prompted: Mapping[str, str] | None = None,
    ) -> int:
        if not command:
            raise ValueError("A command is required")

        child_env = os.environ.copy()
        for binding in bindings:
            name, reference = parse_binding(binding)
            child_env[name] = self.keychain.get(reference)
        if prompted:
            for name, value in prompted.items():
                if not ENV_NAME.fullmatch(name):
                    raise ValueError(f"Invalid environment variable name: {name}")
                child_env[name] = value

        result = subprocess.run(list(command), env=child_env, check=False)
        return result.returncode
