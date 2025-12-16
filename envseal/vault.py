"""Vault repository management."""

from pathlib import Path

from envseal.config import Config


class VaultManager:
    """Manage vault repository structure and paths."""

    def __init__(self, config: Config):
        self.config = config

    def ensure_vault_structure(self) -> None:
        """Ensure vault directory structure exists."""
        secrets_dir = self.config.vault_path / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)

    def get_vault_path(self, repo_name: str, env_name: str) -> Path:
        """Get the vault path for a specific repo and environment."""
        return self.config.vault_path / "secrets" / repo_name / f"{env_name}.env"

    def map_env_filename(self, filename: str) -> str:
        """Map .env filename to environment name using config mapping."""
        # Check if in mapping
        if filename in self.config.env_mapping:
            return self.config.env_mapping[filename]

        # Otherwise, extract from filename (e.g., .env.custom -> custom)
        if filename.startswith(".env."):
            return filename[5:]  # Remove ".env." prefix

        # Default for .env
        return "local"

    def get_repo_vault_dir(self, repo_name: str) -> Path:
        """Get the vault directory for a specific repo."""
        return self.config.vault_path / "secrets" / repo_name
