"""Configuration management for envseal."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Repo:
    """Repository configuration."""

    name: str
    path: Path

    def __post_init__(self) -> None:
        if isinstance(self.path, str):
            self.path = Path(self.path)


@dataclass
class ScanConfig:
    """Scan configuration."""

    include_patterns: list[str] = field(default_factory=lambda: [".env", ".env.*"])
    exclude_patterns: list[str] = field(default_factory=lambda: [".env.example", ".env.sample"])
    ignore_dirs: list[str] = field(
        default_factory=lambda: [".git", "node_modules", "venv", ".venv"]
    )


@dataclass
class Config:
    """Main configuration for envseal."""

    vault_path: Path
    repos: list[Repo] = field(default_factory=list)
    env_mapping: dict[str, str] = field(
        default_factory=lambda: {
            ".env": "local",
            ".env.dev": "dev",
            ".env.development": "dev",
            ".env.staging": "staging",
            ".env.prod": "prod",
            ".env.production": "prod",
        }
    )
    scan: ScanConfig = field(default_factory=ScanConfig)

    def __post_init__(self) -> None:
        if isinstance(self.vault_path, str):
            self.vault_path = Path(self.vault_path)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Load config from dictionary."""
        repos = [Repo(**repo) for repo in data.get("repos", [])]
        scan_data = data.get("scan", {})
        scan = ScanConfig(**scan_data) if scan_data else ScanConfig()

        # Get env_mapping from data or use default
        env_mapping = data.get("env_mapping")
        if env_mapping is None:
            # Use default env_mapping
            env_mapping = {
                ".env": "local",
                ".env.dev": "dev",
                ".env.development": "dev",
                ".env.staging": "staging",
                ".env.prod": "prod",
                ".env.production": "prod",
            }

        return cls(
            vault_path=Path(data["vault_path"]),
            repos=repos,
            env_mapping=env_mapping,
            scan=scan,
        )

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "vault_path": str(self.vault_path),
            "repos": [{"name": r.name, "path": str(r.path)} for r in self.repos],
            "env_mapping": self.env_mapping,
            "scan": {
                "include_patterns": self.scan.include_patterns,
                "exclude_patterns": self.scan.exclude_patterns,
                "ignore_dirs": self.scan.ignore_dirs,
            },
        }

    def save(self, path: Path) -> None:
        """Save config to YAML file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
        except OSError as e:
            raise OSError(f"Failed to save config to {path}: {e}") from e

    @classmethod
    def load(cls, path: Path) -> "Config":
        """Load config from YAML file."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)

            if not data:
                raise ValueError(f"Config file is empty or invalid: {path}")

            if "vault_path" not in data:
                raise ValueError("Config file missing required field: vault_path")

            return cls.from_dict(data)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Config file not found: {path}") from e
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}") from e

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the default config path."""
        return Path.home() / ".config" / "envseal" / "config.yaml"
