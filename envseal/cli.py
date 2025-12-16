"""Command-line interface for envseal."""

import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm

from envseal import __version__
from envseal.config import Config, Repo
from envseal.crypto import AgeKeyManager
from envseal.scanner import Scanner
from envseal.vault import VaultManager
from envseal.sops import SopsManager

app = typer.Typer(
    name="envseal",
    help="Manage encrypted .env files across multiple repositories",
    add_completion=False,
)

console = Console()


def version_callback(value: bool):
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
):
    """EnvSeal - Manage encrypted .env files across repositories."""
    pass


@app.command()
def init(
    root_dir: Optional[Path] = typer.Option(
        None,
        "--root",
        help="Root directory to scan for repositories",
    ),
):
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
        console.print(f"\n⚠️  [yellow]IMPORTANT: Back up this key! You'll need it on other devices.[/yellow]")
        console.print(f"Public key: [cyan]{public_key}[/cyan]")

    # 2. Scan for repositories
    if root_dir is None:
        root_dir = Path.cwd()

    console.print(f"\n🔍 Scanning for Git repositories in {root_dir}...")
    scanner = Scanner(Config().scan)
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
        console.print(f"✅ Created .sops.yaml in vault")

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
):
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
            with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as tmp:
                tmp_path = Path(tmp.name)

                # Parse and write normalized
                data = dotenv_io.parse(env_file.filepath)
                dotenv_io.write(tmp_path, data)

                # Encrypt
                sops.encrypt(tmp_path, vault_path)
                tmp_path.unlink()

            console.print(f"  ✓ {env_file.filename} → {env_name}.env")

    console.print("\n✅ [bold green]Push complete![/bold green]")
    console.print(f"\n📦 Next steps:")
    console.print(f"  1. cd {config.vault_path}")
    console.print("  2. git add .")
    console.print("  3. git commit -m 'Update secrets'")
    console.print("  4. git push")


if __name__ == "__main__":
    app()
