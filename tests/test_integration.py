"""End-to-end integration tests."""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from envseal.config import Config, Repo
from envseal.crypto import AgeKeyManager

runner = CliRunner()

# Check if external tools are available
HAS_AGE = shutil.which("age-keygen") is not None
HAS_SOPS = shutil.which("sops") is not None

requires_age = pytest.mark.skipif(not HAS_AGE, reason="age-keygen not installed")
requires_sops = pytest.mark.skipif(not HAS_SOPS, reason="sops not installed")


@pytest.mark.integration
@requires_age
@requires_sops
def test_full_workflow(temp_dir):
    """Test complete workflow: init -> push -> status -> pull."""
    # Setup test environment
    vault_path = temp_dir / "vault"
    vault_path.mkdir()

    repo_path = temp_dir / "test-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    (repo_path / ".env").write_text("DATABASE_URL=postgres://localhost/db\nAPI_KEY=secret123\n")

    # Override config path
    config_path = temp_dir / "config.yaml"

    # Generate age key
    key_manager = AgeKeyManager()
    key_file = temp_dir / "age-key.txt"
    public_key = key_manager.generate_key(key_file)

    # Create config manually (simpler than interactive init)
    config = Config(
        vault_path=vault_path,
        repos=[Repo(name="test-repo", path=repo_path)],
    )
    config.save(config_path)

    # Create .sops.yaml
    from envseal.sops import SopsManager

    sops = SopsManager(age_public_key=public_key, age_key_file=key_file)
    sops.create_sops_yaml(vault_path / ".sops.yaml")

    # Test that we can run the workflow
    # (Full CLI testing would require more mocking)

    # This is a placeholder - actual CLI integration would need more setup
    assert config_path.exists()
    assert (vault_path / ".sops.yaml").exists()


@pytest.mark.integration
@requires_age
@requires_sops
def test_encryption_decryption_workflow(temp_dir):
    """Test encrypt-decrypt workflow with actual files."""
    # Setup
    vault_path = temp_dir / "vault"
    vault_path.mkdir()
    (vault_path / "secrets").mkdir()

    repo_path = temp_dir / "test-repo"
    repo_path.mkdir()

    # Create test .env file
    env_file = repo_path / ".env.prod"
    env_content = "API_KEY=super-secret-key\nDB_PASSWORD=very-secure-123\n"
    env_file.write_text(env_content)

    # Generate age key
    key_manager = AgeKeyManager()
    key_file = temp_dir / "age-key.txt"
    public_key = key_manager.generate_key(key_file)

    # Test encryption
    from envseal.dotenvio import DotEnvIO
    from envseal.sops import SopsManager

    sops = SopsManager(age_public_key=public_key, age_key_file=key_file)
    dotenv_io = DotEnvIO()

    # Normalize
    normalized = dotenv_io.normalize(env_file)

    # Write to temp file for encryption
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as tmp:
        tmp.write(normalized)
        tmp_path = Path(tmp.name)

    # Encrypt
    encrypted_path = vault_path / "secrets" / "test.env"
    sops.encrypt(tmp_path, encrypted_path)
    tmp_path.unlink()

    # Verify encrypted file exists and contains SOPS metadata
    assert encrypted_path.exists()
    encrypted_content = encrypted_path.read_text()
    assert "sops" in encrypted_content
    assert "age" in encrypted_content

    # Decrypt
    decrypted = sops.decrypt(encrypted_path)

    # Verify decrypted content matches original (normalized)
    assert "API_KEY=" in decrypted
    assert "DB_PASSWORD=" in decrypted
    # Values should be present but we don't expose them in assertions
    assert decrypted.strip() == normalized.strip()


@pytest.mark.integration
def test_scanner_and_vault_integration(temp_dir):
    """Test scanner finding files and vault path mapping."""
    # Setup repo with multiple env files
    repo_path = temp_dir / "multi-env-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()

    (repo_path / ".env").write_text("KEY=local\n")
    (repo_path / ".env.dev").write_text("KEY=dev\n")
    (repo_path / ".env.prod").write_text("KEY=prod\n")
    (repo_path / ".env.example").write_text("KEY=example\n")  # Should be excluded

    # Scan
    from envseal.config import ScanConfig
    from envseal.scanner import Scanner

    scanner = Scanner(ScanConfig())
    env_files = scanner.scan_repo(repo_path)

    # Should find 3 files (.env.example should be excluded)
    assert len(env_files) == 3
    filenames = {ef.filename for ef in env_files}
    assert ".env" in filenames
    assert ".env.dev" in filenames
    assert ".env.prod" in filenames
    assert ".env.example" not in filenames

    # Test vault mapping
    vault_path = temp_dir / "vault"
    config = Config(vault_path=vault_path)

    from envseal.vault import VaultManager

    vault_manager = VaultManager(config)

    # Test mapping
    assert vault_manager.map_env_filename(".env") == "local"
    assert vault_manager.map_env_filename(".env.dev") == "dev"
    assert vault_manager.map_env_filename(".env.prod") == "prod"

    # Test vault paths
    assert (
        vault_manager.get_vault_path("test-repo", "prod")
        == vault_path / "secrets" / "test-repo" / "prod.env"
    )


@pytest.mark.integration
def test_diff_workflow(temp_dir):
    """Test diff calculation between local and vault."""
    # Create vault file
    vault_path = temp_dir / "vault"
    (vault_path / "secrets" / "repo").mkdir(parents=True)
    vault_file = vault_path / "secrets" / "repo" / "prod.env"

    vault_content = "KEY1=value1\nKEY2=value2\nKEY3=value3\n"
    vault_file.write_text(vault_content)

    # Create local file with changes
    local_file = temp_dir / ".env.prod"
    local_content = (
        "KEY1=modified\nKEY2=value2\nKEY4=newkey\n"  # KEY1 modified, KEY3 removed, KEY4 added
    )
    local_file.write_text(local_content)

    # Calculate diff
    from envseal.diffing import DiffCalculator
    from envseal.dotenvio import DotEnvIO

    dotenv_io = DotEnvIO()
    diff_calc = DiffCalculator()

    # Normalize both
    vault_normalized = dotenv_io.normalize(vault_file)
    local_normalized = dotenv_io.normalize(local_file)

    # Calculate diff
    diff = diff_calc.calculate(vault_normalized, local_normalized)

    # Verify diff
    assert "KEY4" in diff.added
    assert "KEY3" in diff.removed
    assert "KEY1" in diff.modified
    assert len(diff.added) == 1
    assert len(diff.removed) == 1
    assert len(diff.modified) == 1


@pytest.mark.integration
@requires_age
@requires_sops
def test_push_skips_unchanged_and_commits(temp_dir, monkeypatch):
    """push encrypts + commits with --commit, then skips unchanged files on re-run."""
    import subprocess

    from envseal.cli import app
    from envseal.sops import SopsManager

    # age key at a temp location
    key_file = temp_dir / "age-key.txt"
    public_key = AgeKeyManager().generate_key(key_file)
    monkeypatch.setattr(AgeKeyManager, "get_default_key_path", lambda self: key_file)

    # project repo with a .env file
    repo_path = temp_dir / "proj"
    repo_path.mkdir()
    (repo_path / ".env").write_text("API_KEY=secret\nDB=postgres://localhost/x\n")

    # git-backed vault with a .sops.yaml
    vault_path = temp_dir / "vault"
    (vault_path / "secrets").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=vault_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=vault_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=vault_path, check=True)
    SopsManager(age_public_key=public_key, age_key_file=key_file).create_sops_yaml(
        vault_path / ".sops.yaml"
    )

    # config at a temp location
    config_path = temp_dir / "config.yaml"
    Config(vault_path=vault_path, repos=[Repo(name="proj", path=repo_path)]).save(config_path)
    monkeypatch.setattr(Config, "get_config_path", staticmethod(lambda: config_path))

    vault_file = vault_path / "secrets" / "proj" / "local.env"

    # first push with --commit: file gets encrypted and committed
    result = runner.invoke(app, ["push", "--commit"])
    assert result.exit_code == 0, result.output
    assert vault_file.exists()
    encrypted_first = vault_file.read_text()
    assert "sops" in encrypted_first

    log = subprocess.run(
        ["git", "-C", str(vault_path), "log", "--oneline"],
        capture_output=True,
        text=True,
    )
    assert log.stdout.strip(), "expected a commit in the vault"

    # second push with no changes: file must NOT be re-encrypted
    result2 = runner.invoke(app, ["push"])
    assert result2.exit_code == 0, result2.output
    assert "no changes" in result2.output.lower()
    assert vault_file.read_text() == encrypted_first
