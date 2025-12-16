"""Repository and .env file scanning."""

import fnmatch
import hashlib
from dataclasses import dataclass
from pathlib import Path

from envseal.config import ScanConfig


@dataclass
class EnvFile:
    """Represents a found .env file."""

    filepath: Path
    repo_path: Path

    @property
    def filename(self) -> str:
        """Get the filename."""
        return self.filepath.name

    def get_hash(self) -> str:
        """Get SHA256 hash of file contents."""
        return hashlib.sha256(self.filepath.read_bytes()).hexdigest()


class Scanner:
    """Scanner for finding .env files in repositories."""

    def __init__(self, scan_config: ScanConfig):
        self.config = scan_config

    def scan_repo(self, repo_path: Path) -> list[EnvFile]:
        """Scan a repository for .env files."""
        env_files = []

        for path in repo_path.rglob("*"):
            # Skip if in ignored directory
            if any(ignored in path.parts for ignored in self.config.ignore_dirs):
                continue

            # Skip if not a file
            if not path.is_file():
                continue

            # Check if matches include patterns
            filename = path.name
            if not any(
                fnmatch.fnmatch(filename, pattern) for pattern in self.config.include_patterns
            ):
                continue

            # Check if matches exclude patterns
            if any(fnmatch.fnmatch(filename, pattern) for pattern in self.config.exclude_patterns):
                continue

            env_files.append(EnvFile(filepath=path, repo_path=repo_path))

        return env_files

    def find_git_repos(self, root_path: Path) -> list[Path]:
        """Find all Git repositories under a root path."""
        repos = []

        for path in root_path.rglob(".git"):
            if path.is_dir():
                repo_path = path.parent
                repos.append(repo_path)

        return repos
