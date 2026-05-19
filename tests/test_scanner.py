"""Tests for repository and .env file scanning."""

from envseal.config import ScanConfig
from envseal.scanner import Scanner


def test_scanner_finds_env_files(mock_repo):
    """Test scanner finds .env files in a repository."""
    scan_config = ScanConfig()
    scanner = Scanner(scan_config)

    env_files = scanner.scan_repo(mock_repo)

    assert len(env_files) == 2
    filenames = {ef.filepath.name for ef in env_files}
    assert ".env" in filenames
    assert ".env.prod" in filenames


def test_scanner_excludes_patterns(temp_dir):
    """Test scanner excludes files matching patterns."""
    repo = temp_dir / "repo"
    repo.mkdir()

    # Create files
    (repo / ".env").write_text("KEY=value")
    (repo / ".env.example").write_text("KEY=example")

    scan_config = ScanConfig(exclude_patterns=[".env.example"])
    scanner = Scanner(scan_config)

    env_files = scanner.scan_repo(repo)

    assert len(env_files) == 1
    assert env_files[0].filepath.name == ".env"


def test_scanner_ignores_directories(temp_dir):
    """Test scanner ignores specified directories."""
    repo = temp_dir / "repo"
    repo.mkdir()
    (repo / "node_modules").mkdir()

    (repo / ".env").write_text("KEY=value")
    (repo / "node_modules" / ".env").write_text("KEY=bad")

    scan_config = ScanConfig(ignore_dirs=["node_modules"])
    scanner = Scanner(scan_config)

    env_files = scanner.scan_repo(repo)

    assert len(env_files) == 1
    assert "node_modules" not in str(env_files[0].filepath)


def test_find_git_repos(temp_dir):
    """Test finding Git repositories."""
    root = temp_dir / "projects"
    root.mkdir()

    # Create nested repos
    (root / "repo1" / ".git").mkdir(parents=True)
    (root / "repo2" / ".git").mkdir(parents=True)
    (root / "not-a-repo").mkdir()

    scanner = Scanner(ScanConfig())
    repos = scanner.find_git_repos(root)

    assert len(repos) == 2
    repo_names = {r.name for r in repos}
    assert "repo1" in repo_names
    assert "repo2" in repo_names


def test_env_file_hash(temp_dir):
    """Test EnvFile hash generation."""
    repo = temp_dir / "repo"
    repo.mkdir()
    env_file = repo / ".env"
    env_file.write_text("KEY=value\n")

    scanner = Scanner(ScanConfig())
    files = scanner.scan_repo(repo)

    assert len(files) == 1
    hash1 = files[0].get_hash()

    # Hash should be consistent
    hash2 = files[0].get_hash()
    assert hash1 == hash2

    # Hash should be SHA256 (64 hex chars)
    assert len(hash1) == 64
    assert all(c in "0123456789abcdef" for c in hash1)


def test_scanner_empty_repo(temp_dir):
    """Test scanning empty repository."""
    repo = temp_dir / "empty"
    repo.mkdir()

    scanner = Scanner(ScanConfig())
    files = scanner.scan_repo(repo)

    assert len(files) == 0


def test_scanner_skips_backup_files(temp_dir):
    """Backup files left by `pull --replace` must not be scanned as env files."""
    repo = temp_dir / "repo"
    repo.mkdir()

    (repo / ".env").write_text("KEY=value")
    (repo / ".env.prod").write_text("KEY=prod")
    # files that `envseal pull --replace` writes:
    (repo / ".env.backup").write_text("KEY=old")
    (repo / ".env.prod.backup").write_text("KEY=old")

    scanner = Scanner(ScanConfig())
    found = {ef.filepath.name for ef in scanner.scan_repo(repo)}

    assert found == {".env", ".env.prod"}
    assert ".env.backup" not in found
    assert ".env.prod.backup" not in found


def test_scanner_skips_template_files(temp_dir):
    """`.example` / `.sample` template files must not be scanned as env files."""
    repo = temp_dir / "repo"
    repo.mkdir()

    (repo / ".env").write_text("KEY=value")
    (repo / ".env.prod").write_text("KEY=prod")
    # templates with placeholder values, not real secrets:
    (repo / ".env.example").write_text("KEY=")
    (repo / ".env.production.example").write_text("KEY=")
    (repo / ".env.sample").write_text("KEY=")

    scanner = Scanner(ScanConfig())
    found = {ef.filepath.name for ef in scanner.scan_repo(repo)}

    assert found == {".env", ".env.prod"}


def test_scanner_recurses_and_records_subdir(temp_dir):
    """Scanner recurses; each file records its subdir for a distinct vault path."""
    repo = temp_dir / "repo"
    (repo / "sub" / "deep").mkdir(parents=True)
    (repo / ".env").write_text("KEY=root")
    (repo / "sub" / ".env").write_text("KEY=nested")
    (repo / "sub" / "deep" / ".env").write_text("KEY=deeper")

    scanner = Scanner(ScanConfig())
    found = {str(ef.subdir): ef for ef in scanner.scan_repo(repo)}

    assert set(found) == {".", "sub", "sub/deep"}
    assert found["."].filepath == repo / ".env"
    assert found["sub"].filepath == repo / "sub" / ".env"
