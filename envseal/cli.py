"""Command-line interface for envseal."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt

from envseal import __version__
from envseal.config import Config, Repo
from envseal.crypto import AgeKeyManager
from envseal.scanner import Scanner
from envseal.sops import SopsManager
from envseal.vault import VaultManager

app = typer.Typer(
    name="envseal",
    help="Manage encrypted .env files across multiple repositories",
    add_completion=False,
)

console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        typer.echo(f"envseal version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """EnvSeal - Manage encrypted .env files across repositories."""
    pass


@app.command()
def init(
    root_dir: Optional[Path] = typer.Option(
        None,
        "--root",
        help="Root directory to scan for repositories",
    ),
) -> None:
    """Initialize envseal configuration."""
    console.print("🔍 [bold]Initializing envseal...[/bold]")

    # 1. Check/generate age key
    console.print("\n🔐 Checking age encryption key...")
    key_manager = AgeKeyManager()
    key_path = key_manager.get_default_key_path()

    if key_manager.key_exists(key_path):
        console.print(f"✅ Age key found at {key_path}")
        public_key = key_manager.get_public_key(key_path)
    else:
        console.print("No age key found. Generating new key...")
        public_key = key_manager.generate_key(key_path)
        console.print(f"✅ Age key created: {key_path}")
        console.print(
            "\n⚠️  [yellow]IMPORTANT: Back up this key! You'll need it on other devices.[/yellow]"
        )
        console.print(f"Public key: [cyan]{public_key}[/cyan]")

    # 2. Scan for repositories
    if root_dir is None:
        root_dir = Path.cwd()

    console.print(f"\n🔍 Scanning for Git repositories in {root_dir}...")
    from envseal.config import ScanConfig

    scanner = Scanner(ScanConfig())
    repos = scanner.find_git_repos(root_dir)

    if not repos:
        console.print("[red]No Git repositories found.[/red]")
        raise typer.Exit(1)

    console.print(f"Found {len(repos)} repositories:")
    for i, repo in enumerate(repos, 1):
        console.print(f"  [{i}] {repo.name} ({repo})")

    # 3. Get vault path
    console.print("\n📝 Where is your secrets-vault repository?")
    vault_path_str = Prompt.ask(
        "Path",
        default=str(Path.home() / "Github" / "secrets-vault"),
    )
    vault_path = Path(vault_path_str).expanduser()

    # 4. Create config
    config = Config(
        vault_path=vault_path,
        repos=[Repo(name=repo.name, path=repo) for repo in repos],
    )

    config_path = Config.get_config_path()
    config.save(config_path)
    console.print(f"\n✅ Configuration saved to {config_path}")

    # 5. Setup vault
    vault_manager = VaultManager(config)
    vault_manager.ensure_vault_structure()

    sops_yaml_path = vault_path / ".sops.yaml"
    if not sops_yaml_path.exists():
        sops = SopsManager(age_public_key=public_key, age_key_file=key_path)
        sops.create_sops_yaml(sops_yaml_path)
        console.print("✅ Created .sops.yaml in vault")

    console.print("\n✅ [bold green]Initialization complete![/bold green]")
    console.print("\n📦 Next steps:")
    console.print("  1. Run: [cyan]envseal push[/cyan] to sync secrets to vault")
    console.print(f"  2. cd {vault_path}")
    console.print("  3. git add . && git commit -m 'Initial secrets import'")
    console.print("  4. git push")


@app.command()
def push(
    repos: Optional[list[str]] = typer.Argument(
        None,
        help="Specific repos to push (default: all)",
    ),
    env: Optional[str] = typer.Option(
        None,
        "--env",
        help="Only push specific environment (e.g., prod)",
    ),
) -> None:
    """Push .env files to vault and encrypt with SOPS."""
    console.print("🔄 [bold]Pushing secrets to vault...[/bold]")

    # Load config
    config_path = Config.get_config_path()
    if not config_path.exists():
        console.print("[red]Config not found. Run 'envseal init' first.[/red]")
        raise typer.Exit(1)

    config = Config.load(config_path)

    # Get age key
    key_manager = AgeKeyManager()
    key_path = key_manager.get_default_key_path()
    if not key_manager.key_exists(key_path):
        console.print("[red]Age key not found. Run 'envseal init' first.[/red]")
        raise typer.Exit(1)

    public_key = key_manager.get_public_key(key_path)

    # Initialize managers
    scanner = Scanner(config.scan)
    vault_manager = VaultManager(config)
    sops = SopsManager(age_public_key=public_key, age_key_file=key_path)

    from envseal.dotenvio import DotEnvIO

    dotenv_io = DotEnvIO()

    # Process each repo
    repos_to_process = config.repos
    if repos:
        repos_to_process = [r for r in config.repos if r.name in repos]

    for repo in repos_to_process:
        console.print(f"\n📁 Processing [cyan]{repo.name}[/cyan]...")

        # Scan for .env files
        env_files = scanner.scan_repo(repo.path)

        if not env_files:
            console.print("  No .env files found")
            continue

        for env_file in env_files:
            env_name = vault_manager.map_env_filename(env_file.filename)

            # Skip if --env specified and doesn't match
            if env and env_name != env:
                continue

            # Get vault path
            vault_path = vault_manager.get_vault_path(repo.name, env_name)
            vault_path.parent.mkdir(parents=True, exist_ok=True)

            # Normalize and encrypt
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as tmp:
                tmp_path = Path(tmp.name)

                # Parse and write normalized
                data = dotenv_io.parse(env_file.filepath)
                dotenv_io.write(tmp_path, data)

                # Encrypt
                sops.encrypt(tmp_path, vault_path)
                tmp_path.unlink()

            console.print(f"  ✓ {env_file.filename} → {env_name}.env")

    console.print("\n✅ [bold green]Push complete![/bold green]")
    console.print("\n📦 Next steps:")
    console.print(f"  1. cd {config.vault_path}")
    console.print("  2. git add .")
    console.print("  3. git commit -m 'Update secrets'")
    console.print("  4. git push")


@app.command()
def status() -> None:
    """Show status of secrets compared to vault."""
    console.print("📊 [bold]Checking secrets status...[/bold]\n")

    # Load config
    config_path = Config.get_config_path()
    if not config_path.exists():
        console.print("[red]Config not found. Run 'envseal init' first.[/red]")
        raise typer.Exit(1)

    config = Config.load(config_path)

    # Get age key
    key_manager = AgeKeyManager()
    key_path = key_manager.get_default_key_path()
    public_key = key_manager.get_public_key(key_path)

    # Initialize managers
    scanner = Scanner(config.scan)
    vault_manager = VaultManager(config)
    sops = SopsManager(age_public_key=public_key, age_key_file=key_path)

    from envseal.diffing import DiffCalculator
    from envseal.dotenvio import DotEnvIO

    dotenv_io = DotEnvIO()
    diff_calc = DiffCalculator()

    # Process each repo
    for repo in config.repos:
        console.print(f"[cyan]{repo.name}[/cyan]")

        env_files = scanner.scan_repo(repo.path)

        for env_file in env_files:
            env_name = vault_manager.map_env_filename(env_file.filename)
            vault_path = vault_manager.get_vault_path(repo.name, env_name)

            if not vault_path.exists():
                console.print(f"  + [yellow]{env_file.filename}[/yellow] - new file (not in vault)")
                continue

            # Compare with vault
            local_normalized = dotenv_io.normalize(env_file.filepath)
            vault_decrypted = sops.decrypt(vault_path)

            diff = diff_calc.calculate(vault_decrypted, local_normalized)

            if diff.is_clean():
                console.print(f"  ✓ [green]{env_file.filename}[/green] - up to date")
            else:
                num_changes = len(diff.added) + len(diff.removed) + len(diff.modified)
                console.print(
                    f"  ⚠ [yellow]{env_file.filename}[/yellow] - {num_changes} keys changed"
                )

        console.print()

    console.print("Use [cyan]'envseal diff <repo>'[/cyan] to see details.")


@app.command()
def diff(
    repo_name: str = typer.Argument(..., help="Repository name"),
    env: str = typer.Option("prod", "--env", help="Environment to diff"),
) -> None:
    """Show key-only diff for a specific repo and environment."""
    console.print(f"📝 [bold]Changes in {repo_name}/{env}.env[/bold]\n")

    # Load config
    config_path = Config.get_config_path()
    config = Config.load(config_path)

    # Find repo
    repo = next((r for r in config.repos if r.name == repo_name), None)
    if not repo:
        console.print(f"[red]Repository '{repo_name}' not found in config.[/red]")
        raise typer.Exit(1)

    # Get managers
    key_manager = AgeKeyManager()
    key_path = key_manager.get_default_key_path()
    public_key = key_manager.get_public_key(key_path)

    scanner = Scanner(config.scan)
    vault_manager = VaultManager(config)
    sops = SopsManager(age_public_key=public_key, age_key_file=key_path)

    from envseal.diffing import DiffCalculator
    from envseal.dotenvio import DotEnvIO

    dotenv_io = DotEnvIO()
    diff_calc = DiffCalculator()

    # Find local file
    env_files = scanner.scan_repo(repo.path)
    local_file = next(
        (ef for ef in env_files if vault_manager.map_env_filename(ef.filename) == env), None
    )

    if not local_file:
        console.print(f"[red]No .env file for '{env}' environment found locally.[/red]")
        raise typer.Exit(1)

    # Get vault file
    vault_path = vault_manager.get_vault_path(repo_name, env)
    if not vault_path.exists():
        console.print("[yellow]File not in vault yet. All keys are new.[/yellow]")
        raise typer.Exit(0)

    # Calculate diff
    local_normalized = dotenv_io.normalize(local_file.filepath)
    vault_decrypted = sops.decrypt(vault_path)

    diff_result = diff_calc.calculate(vault_decrypted, local_normalized)

    if diff_result.is_clean():
        console.print("[green]No changes[/green]")
        return

    # Show diff
    if diff_result.added:
        console.print("[green]+ ADDED:[/green]")
        for key in sorted(diff_result.added):
            console.print(f"  - {key}")
        console.print()

    if diff_result.modified:
        console.print("[yellow]~ MODIFIED:[/yellow]")
        for key in sorted(diff_result.modified):
            console.print(f"  - {key}")
        console.print()

    if diff_result.removed:
        console.print("[red]- REMOVED:[/red]")
        for key in sorted(diff_result.removed):
            console.print(f"  - {key}")
        console.print()

    console.print(f"Use [cyan]'envseal push {repo_name} --env {env}'[/cyan] to sync.")


@app.command()
def pull(
    repo_name: str = typer.Argument(..., help="Repository name"),
    env: str = typer.Option("prod", "--env", help="Environment to pull"),
    replace: bool = typer.Option(False, "--replace", help="Replace local .env file"),
    stdout: bool = typer.Option(False, "--stdout", help="Output to stdout"),
) -> None:
    """Pull and decrypt secrets from vault."""
    # Load config
    config_path = Config.get_config_path()
    config = Config.load(config_path)

    # Find repo
    repo = next((r for r in config.repos if r.name == repo_name), None)
    if not repo:
        console.print(f"[red]Repository '{repo_name}' not found.[/red]")
        raise typer.Exit(1)

    # Get managers
    key_manager = AgeKeyManager()
    key_path = key_manager.get_default_key_path()
    public_key = key_manager.get_public_key(key_path)

    vault_manager = VaultManager(config)
    sops = SopsManager(age_public_key=public_key, age_key_file=key_path)

    # Get vault file
    vault_path = vault_manager.get_vault_path(repo_name, env)
    if not vault_path.exists():
        console.print(f"[red]No vault file for {repo_name}/{env}[/red]")
        raise typer.Exit(1)

    # Decrypt
    decrypted = sops.decrypt(vault_path)

    if stdout:
        # Output to stdout
        console.print(decrypted, end="")
    elif replace:
        # Replace local file
        # Find the corresponding local file
        env_filename = None
        for pattern, mapped_env in config.env_mapping.items():
            if mapped_env == env:
                env_filename = pattern
                break

        if not env_filename:
            env_filename = f".env.{env}"

        local_path = repo.path / env_filename

        # Backup existing file
        if local_path.exists():
            backup_path = local_path.with_suffix(local_path.suffix + ".backup")
            import shutil

            shutil.copy2(local_path, backup_path)
            console.print(f"✓ Backed up to {backup_path}")

        local_path.write_text(decrypted)
        console.print(f"✅ Pulled to {local_path}")
    else:
        # Write to temp directory
        import tempfile

        temp_dir = Path(tempfile.mkdtemp(prefix="envseal-"))
        temp_file = temp_dir / f"{env}.env"
        temp_file.write_text(decrypted)

        console.print(f"✅ Decrypted to: [cyan]{temp_file}[/cyan]")
        console.print("\n⚠️  Temporary file will be deleted when process ends.")


if __name__ == "__main__":
    app()
