"""Command-line interface for envseal."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt

from envseal import __version__
from envseal.changes import ChangeCollector, ChangeInfo
from envseal.config import Config, Repo
from envseal.crypto import AgeKeyManager
from envseal.diffing import DiffCalculator
from envseal.dotenvio import DotEnvIO
from envseal.interactive import InteractiveSelector, SelectionItem
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


def _sync_vault(
    vault_manager: VaultManager,
    config: Config,
    commit: bool,
    do_push: bool,
    message: str,
) -> None:
    """Commit (and optionally push) the vault repo, or print manual git steps.

    When neither --commit nor --push is passed the previous behaviour is kept:
    the manual git steps are printed for the user to run themselves.
    """
    if not commit and not do_push:
        console.print("\n📦 Next steps:")
        console.print(f"  1. cd {config.vault_path}")
        console.print("  2. git add .")
        console.print("  3. git commit -m 'Update secrets'")
        console.print("  4. git push")
        return

    if not vault_manager.is_git_repo():
        console.print(
            f"\n[yellow]⚠ Vault at {config.vault_path} is not a Git repository "
            "— skipping commit.[/yellow]"
        )
        return

    try:
        if vault_manager.git_commit(message):
            console.print("\n✅ Committed changes in vault")
        else:
            console.print("\n[dim]Vault: nothing to commit.[/dim]")
        if do_push:
            vault_manager.git_push()
            console.print("✅ Pushed vault to remote")
    except RuntimeError as e:
        console.print(f"\n[red]Git operation failed: {e}[/red]")
        console.print(
            f"[yellow]Run manually: cd {config.vault_path} "
            "&& git add . && git commit && git push[/yellow]"
        )


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
    commit: bool = typer.Option(
        False,
        "--commit",
        help="Commit the encrypted changes in the vault repo",
    ),
    do_push: bool = typer.Option(
        False,
        "--push",
        help="Commit and push the vault repo to its remote",
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
    dotenv_io = DotEnvIO()
    diff_calc = DiffCalculator()

    # Process each repo
    repos_to_process = config.repos
    if repos:
        repos_to_process = [r for r in config.repos if r.name in repos]

    pushed_count = 0
    skipped_count = 0

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

            # Vault path mirrors the file's location within the repo
            subdir = str(env_file.subdir)
            loc = f"{env_file.subdir}/" if env_file.subdir.parts else ""
            vault_path = vault_manager.get_vault_path(repo.name, env_name, subdir)

            # Skip unchanged files: SOPS encryption is non-deterministic, so
            # re-encrypting an unchanged file still produces a noisy git diff.
            if vault_path.exists():
                local_normalized = dotenv_io.normalize(env_file.filepath)
                vault_decrypted = sops.decrypt(vault_path)
                if diff_calc.calculate(vault_decrypted, local_normalized).is_clean():
                    console.print(
                        f"  ⊘ [dim]{loc}{env_file.filename} → {loc}{env_name}.env (no changes)[/dim]"
                    )
                    skipped_count += 1
                    continue

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

            console.print(f"  ✓ {loc}{env_file.filename} → {loc}{env_name}.env")
            pushed_count += 1

    # Summary
    if pushed_count:
        summary = f"Pushed {pushed_count} file(s) to vault"
        if skipped_count:
            summary += f", {skipped_count} unchanged"
        console.print(f"\n✅ [bold green]{summary}[/bold green]")
        _sync_vault(vault_manager, config, commit, do_push, "envseal: update secrets")
    elif skipped_count:
        console.print(f"\n✅ All {skipped_count} file(s) already up to date — nothing to encrypt.")
    else:
        console.print("\n[yellow]Nothing to push.[/yellow]")


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
    if not key_manager.key_exists(key_path):
        console.print("[red]Age key not found. Run 'envseal init' first.[/red]")
        raise typer.Exit(1)
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
            loc = f"{env_file.subdir}/" if env_file.subdir.parts else ""
            vault_path = vault_manager.get_vault_path(repo.name, env_name, str(env_file.subdir))

            if not vault_path.exists():
                console.print(
                    f"  + [yellow]{loc}{env_file.filename}[/yellow] - new file (not in vault)"
                )
                continue

            # Compare with vault
            local_normalized = dotenv_io.normalize(env_file.filepath)
            vault_decrypted = sops.decrypt(vault_path)

            diff = diff_calc.calculate(vault_decrypted, local_normalized)

            if diff.is_clean():
                console.print(f"  ✓ [green]{loc}{env_file.filename}[/green] - up to date")
            else:
                num_changes = len(diff.added) + len(diff.removed) + len(diff.modified)
                console.print(
                    f"  ⚠ [yellow]{loc}{env_file.filename}[/yellow] - {num_changes} keys changed"
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
    if not config_path.exists():
        console.print("[red]Config not found. Run 'envseal init' first.[/red]")
        raise typer.Exit(1)
    config = Config.load(config_path)

    # Find repo
    repo = next((r for r in config.repos if r.name == repo_name), None)
    if not repo:
        console.print(f"[red]Repository '{repo_name}' not found in config.[/red]")
        raise typer.Exit(1)

    # Get managers
    key_manager = AgeKeyManager()
    key_path = key_manager.get_default_key_path()
    if not key_manager.key_exists(key_path):
        console.print("[red]Age key not found. Run 'envseal init' first.[/red]")
        raise typer.Exit(1)
    public_key = key_manager.get_public_key(key_path)

    scanner = Scanner(config.scan)
    vault_manager = VaultManager(config)
    sops = SopsManager(age_public_key=public_key, age_key_file=key_path)

    from envseal.diffing import DiffCalculator
    from envseal.dotenvio import DotEnvIO

    dotenv_io = DotEnvIO()
    diff_calc = DiffCalculator()

    # Find all local files for this environment (root and any nested)
    env_files = scanner.scan_repo(repo.path)
    matches = [ef for ef in env_files if vault_manager.map_env_filename(ef.filename) == env]

    if not matches:
        console.print(f"[red]No .env file for '{env}' environment found locally.[/red]")
        raise typer.Exit(1)

    for local_file in matches:
        loc = f"{local_file.subdir}/" if local_file.subdir.parts else ""
        console.print(f"[bold cyan]{loc}{local_file.filename}[/bold cyan]")

        vault_path = vault_manager.get_vault_path(repo_name, env, str(local_file.subdir))
        if not vault_path.exists():
            console.print("  [yellow]not in vault yet — all keys are new[/yellow]\n")
            continue

        diff_result = diff_calc.calculate(
            sops.decrypt(vault_path), dotenv_io.normalize(local_file.filepath)
        )
        if diff_result.is_clean():
            console.print("  [green]no changes[/green]\n")
            continue

        if diff_result.added:
            console.print("  [green]+ ADDED:[/green]    " + ", ".join(sorted(diff_result.added)))
        if diff_result.modified:
            console.print(
                "  [yellow]~ MODIFIED:[/yellow] " + ", ".join(sorted(diff_result.modified))
            )
        if diff_result.removed:
            console.print("  [red]- REMOVED:[/red]  " + ", ".join(sorted(diff_result.removed)))
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
    if not config_path.exists():
        console.print("[red]Config not found. Run 'envseal init' first.[/red]")
        raise typer.Exit(1)
    config = Config.load(config_path)

    # Find repo
    repo = next((r for r in config.repos if r.name == repo_name), None)
    if not repo:
        console.print(f"[red]Repository '{repo_name}' not found.[/red]")
        raise typer.Exit(1)

    # Get managers
    key_manager = AgeKeyManager()
    key_path = key_manager.get_default_key_path()
    if not key_manager.key_exists(key_path):
        console.print("[red]Age key not found. Run 'envseal init' first.[/red]")
        raise typer.Exit(1)
    public_key = key_manager.get_public_key(key_path)

    vault_manager = VaultManager(config)
    sops = SopsManager(age_public_key=public_key, age_key_file=key_path)

    # Find every vault file for this repo + environment (root and nested)
    repo_vault_dir = vault_manager.get_repo_vault_dir(repo_name)
    vault_files = sorted(repo_vault_dir.rglob(f"{env}.env")) if repo_vault_dir.is_dir() else []
    if not vault_files:
        console.print(f"[red]No vault file for {repo_name}/{env}[/red]")
        raise typer.Exit(1)

    # Reverse-map the environment name to a local .env filename
    env_filename = next(
        (pattern for pattern, mapped in config.env_mapping.items() if mapped == env),
        f".env.{env}",
    )

    if stdout:
        for vault_file in vault_files:
            sub = vault_file.parent.relative_to(repo_vault_dir)
            if sub.parts:
                console.print(f"# --- {sub}/{env_filename} ---")
            console.print(sops.decrypt(vault_file), end="")
    elif replace:
        import shutil

        for vault_file in vault_files:
            sub = vault_file.parent.relative_to(repo_vault_dir)
            local_path = repo.path / sub / env_filename
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Backup existing file
            if local_path.exists():
                backup_path = local_path.with_suffix(local_path.suffix + ".backup")
                shutil.copy2(local_path, backup_path)
                console.print(f"✓ Backed up to {backup_path}")

            local_path.write_text(sops.decrypt(vault_file))
            console.print(f"✅ Pulled to {local_path}")
    else:
        # Write to a private temp directory (mkdtemp creates it with 0700 perms)
        import os
        import tempfile

        temp_dir = Path(tempfile.mkdtemp(prefix="envseal-"))
        for vault_file in vault_files:
            sub = vault_file.parent.relative_to(repo_vault_dir)
            temp_file = temp_dir / sub / f"{env}.env"
            temp_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file.write_text(sops.decrypt(vault_file))
            os.chmod(temp_file, 0o600)
            console.print(f"✅ Decrypted to: [cyan]{temp_file}[/cyan]")

        console.print(
            "\n⚠️  [yellow]These are plaintext secrets files and are NOT auto-deleted.[/yellow]"
        )
        console.print(f"   Remove them when done: [cyan]rm -rf {temp_dir}[/cyan]")


@app.command()
def update(
    env: Optional[str] = typer.Option(
        None,
        "--env",
        help="Only show changes for specific environment",
    ),
    commit: bool = typer.Option(
        False,
        "--commit",
        help="Commit the encrypted changes in the vault repo",
    ),
    do_push: bool = typer.Option(
        False,
        "--push",
        help="Commit and push the vault repo to its remote",
    ),
) -> None:
    """Interactively update changed secrets to vault."""
    console.print("🔄 Scanning repositories for changes...")

    # Load config
    config_path = Config.get_config_path()
    if not config_path.exists():
        console.print("[red]Config not found. Run 'envseal init' first.[/red]")
        raise typer.Exit(1)

    config = Config.load(config_path)

    # Initialize managers
    key_manager = AgeKeyManager()
    key_path = key_manager.get_default_key_path()

    if not key_manager.key_exists(key_path):
        console.print("[red]Age key not found. Run 'envseal init' first.[/red]")
        raise typer.Exit(1)

    public_key = key_manager.get_public_key(key_path)

    scanner = Scanner(config.scan)
    vault_manager = VaultManager(config)
    sops = SopsManager(age_public_key=public_key, age_key_file=key_path)
    dotenv_io = DotEnvIO()
    diff_calc = DiffCalculator()

    # Collect changes
    change_collector = ChangeCollector(
        config=config,
        scanner=scanner,
        vault_manager=vault_manager,
        sops=sops,
        dotenv_io=dotenv_io,
        diff_calc=diff_calc,
    )

    changes = change_collector.collect_changes(env_filter=env)

    # Check if any changes found
    if not changes:
        console.print("\n✅ All secrets are up to date!")
        return

    # Show summary
    console.print(
        f"\n[bold]Found {len(changes)} {'repository' if len(changes) == 1 else 'repositories'} with changes:[/bold]\n"
    )

    # Build selection items
    items = []
    for change in changes:
        item = SelectionItem(
            id=f"{change.repo_name}/{change.env_name}",
            display=f"{change.repo_name} - {change.env_name}.env",
            description=change.change_summary,
            data=change,
            selected=True,  # Default to all selected
        )
        items.append(item)

    # Show interactive selector
    selector = InteractiveSelector(items, console)
    selected = selector.show()

    # Check if any items selected
    if not selected:
        console.print("\n[yellow]No items selected. Exiting.[/yellow]")
        return

    # Push selected files
    console.print(f"\n🚀 Updating {len(selected)} {'file' if len(selected) == 1 else 'files'}...\n")

    updated_count = 0
    skipped_count = 0

    for item in selected:
        change: ChangeInfo = item.data
        console.print(f"📁 Checking [cyan]{change.repo_name}/{change.env_name}[/cyan]...")

        try:
            # Re-verify that values are actually different before encrypting
            # This prevents unnecessary re-encryption when only formatting differs
            local_normalized = dotenv_io.normalize(change.env_file.filepath)
            vault_decrypted = sops.decrypt(change.vault_path)

            # Re-calculate diff to ensure values are still different
            current_diff = diff_calc.calculate(vault_decrypted, local_normalized)

            # Skip if no actual changes (values might have been changed back)
            if not (current_diff.added or current_diff.modified or current_diff.removed):
                console.print(
                    f"  ⊘ [dim]{change.env_name}.env - no changes detected, skipped[/dim]"
                )
                skipped_count += 1
                continue

            # Ensure vault directory exists
            change.vault_path.parent.mkdir(parents=True, exist_ok=True)

            # Use temp file for encryption (same pattern as push command)
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as tmp:
                tmp_path = Path(tmp.name)

                # Parse and write normalized
                data = dotenv_io.parse(change.env_file.filepath)
                dotenv_io.write(tmp_path, data)

                # Encrypt
                sops.encrypt(tmp_path, change.vault_path)
                tmp_path.unlink()

            console.print(f"  ✓ [green]{change.env_name}.env updated[/green]")
            updated_count += 1

        except Exception as e:
            console.print(f"  ✗ [red]Failed: {e}[/red]")

    # Show summary and next steps
    if updated_count > 0:
        summary_parts = [
            f"Updated {updated_count} {'secret' if updated_count == 1 else 'secrets'} to vault"
        ]
        if skipped_count > 0:
            summary_parts.append(f"skipped {skipped_count} (no changes)")
        console.print(f"\n✅ {', '.join(summary_parts)}")

        _sync_vault(vault_manager, config, commit, do_push, "envseal: update secrets")
    else:
        if skipped_count > 0:
            console.print(
                f"\n✅ All {skipped_count} selected {'file' if skipped_count == 1 else 'files'} already up to date (no re-encryption needed)"
            )
        else:
            console.print("\n[yellow]No files were updated.[/yellow]")


def _collect_overview(
    config: Config, vault_manager: VaultManager, sops: SopsManager
) -> dict[str, list[tuple[str, list[str]]]]:
    """Build {repo: [(relative_path, [key_names]), ...]} from the vault.

    Only key NAMES are collected; decrypted values are never returned, kept or
    written anywhere.
    """
    from io import StringIO

    from dotenv import dotenv_values

    overview: dict[str, list[tuple[str, list[str]]]] = {}
    for repo in config.repos:
        repo_dir = vault_manager.get_repo_vault_dir(repo.name)
        if not repo_dir.is_dir():
            continue
        entries: list[tuple[str, list[str]]] = []
        for vault_file in sorted(repo_dir.rglob("*.env")):
            rel = str(vault_file.relative_to(repo_dir))
            try:
                parsed = dotenv_values(stream=StringIO(sops.decrypt(vault_file)))
                keys = sorted(k for k in parsed if k)
            except Exception:
                keys = []
            entries.append((rel, keys))
        if entries:
            overview[repo.name] = entries
    return overview


def _render_report_html(overview: dict[str, list[tuple[str, list[str]]]]) -> str:
    """Render the key-only overview as a self-contained static HTML page."""
    import html as _html
    from datetime import datetime

    def esc(text: str) -> str:
        return _html.escape(str(text), quote=True)

    repo_count = len(overview)
    key_count = sum(len(keys) for entries in overview.values() for _, keys in entries)
    file_count = sum(len(entries) for entries in overview.values())
    all_envs = {Path(rel).stem for entries in overview.values() for rel, _ in entries}
    env_count = len(all_envs)

    sections: list[str] = []
    for idx, repo_name in enumerate(sorted(overview, key=str.lower)):
        files = overview[repo_name]
        total = sum(len(keys) for _, keys in files)
        safe = esc(repo_name)
        envs = sorted({Path(rel).stem for rel, _ in files})
        all_keys = sorted({k for _, keys in files for k in keys})
        search_blob = esc((repo_name + " " + " ".join(all_keys)).lower())

        env_badges = "".join(f'<span class="tag">{esc(e)}</span>' for e in envs)
        head = (
            f'<button class="repo-head" type="button">'
            f'<span class="caret">&#9656;</span>'
            f'<span class="repo-name">{safe}</span>'
            f'<span class="repo-tags">{env_badges}</span>'
            f'<span class="repo-count">{total}<small>keys</small></span>'
            f"</button>"
        )

        cmd_rows: list[str] = []
        for e in envs:
            restore = f"envseal pull {repo_name} --env {e} --replace"
            copy = f"envseal pull {repo_name} --env {e} --stdout > {repo_name}-{e}.env"
            cmd_rows.append(
                f'<div class="cmd-grp"><span class="cmd-env">{esc(e)}</span>'
                f'<button class="cmd" data-copy="{esc(restore)}" '
                f'title="Copy &mdash; restore into the project directory">'
                f'<span class="cmd-tag">restore</span>'
                f'<code>$ {esc(restore)}</code><span class="cmd-ico">&#9106;</span></button>'
                f'<button class="cmd" data-copy="{esc(copy)}" '
                f'title="Copy &mdash; write a standalone copy">'
                f'<span class="cmd-tag">copy</span>'
                f'<code>$ {esc(copy)}</code><span class="cmd-ico">&#9106;</span></button></div>'
            )
        howto = (
            '<details class="howto"><summary>retrieve commands</summary>'
            + "".join(cmd_rows)
            + "</details>"
        )

        file_blocks: list[str] = []
        for rel, keys in files:
            if keys:
                tags = "".join(f"<code>{esc(k)}</code>" for k in keys)
                body_html = f'<div class="keys">{tags}</div>'
            else:
                body_html = '<div class="keys empty">!! could not read this file</div>'
            file_blocks.append(
                f'<div class="file"><div class="file-head">'
                f'<span class="file-path">{esc(rel)}</span>'
                f'<span class="file-n">{len(keys)}</span></div>{body_html}</div>'
            )

        delay = min(idx, 16) * 45
        sections.append(
            f'<section class="repo" data-search="{search_blob}" '
            f'style="animation-delay:{delay}ms">'
            f'{head}<div class="repo-body">{howto}{"".join(file_blocks)}</div></section>'
        )
    body = (
        "\n".join(sections)
        if sections
        else '<p class="vault-empty">// no secrets in the vault yet</p>'
    )
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    template = """<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EnvSeal // secrets overview</title>
<style>
[data-theme="dark"] {
  --bg: #0a0b0d; --grid: rgba(255,255,255,.022);
  --panel: #101217; --panel-2: #15181e; --panel-3: #1a1e26;
  --line: #23272f; --line-2: #343a44;
  --text: #d8dbe1; --muted: #888e9a; --faint: #565c67;
  --accent: #e8b23c; --accent-2: #f1cd76; --accent-dim: rgba(232,178,60,.13);
  --ok: #5cc97f; --danger: #e7585d;
}
[data-theme="light"] {
  --bg: #e9e7dd; --grid: rgba(40,32,12,.04);
  --panel: #f6f4ea; --panel-2: #efece0; --panel-3: #e7e3d3;
  --line: #d2cdb8; --line-2: #b9b297;
  --text: #262219; --muted: #6a6557; --faint: #989283;
  --accent: #9a6310; --accent-2: #7e5008; --accent-dim: rgba(154,99,16,.11);
  --ok: #3f8f55; --danger: #bb3a3e;
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body {
  --mono: ui-monospace, "SF Mono", SFMono-Regular, "JetBrains Mono", Menlo, Consolas, "Liberation Mono", monospace;
  font-family: var(--mono);
  font-size: 14px; line-height: 1.6; color: var(--text);
  background-color: var(--bg);
  background-image:
    linear-gradient(var(--grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 30px 30px;
  -webkit-font-smoothing: antialiased;
}
::selection { background: var(--accent); color: var(--bg); }
.wrap { max-width: 980px; margin: 0 auto; padding: 2.2rem 1.1rem 5rem; }
a { color: var(--accent); }

/* ---- console header ---- */
.console {
  border: 1px solid var(--line); border-top: 2px solid var(--accent);
  background: var(--panel); padding: 1.3rem 1.5rem 1.5rem;
}
.titlebar {
  display: flex; align-items: center; gap: .7rem;
  border-bottom: 1px solid var(--line); padding-bottom: .7rem; margin-bottom: 1.2rem;
}
.brand { color: var(--accent); font-weight: 700; letter-spacing: .22em; font-size: .82rem; }
.leader { flex: 1; border-bottom: 1px dashed var(--line-2); height: 1px; }
#theme {
  font: inherit; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase;
  background: transparent; color: var(--muted); border: 1px solid var(--line);
  padding: .35rem .7rem; cursor: pointer;
}
#theme:hover { color: var(--accent); border-color: var(--accent); }
.headline {
  font-size: clamp(1.7rem, 4.2vw, 2.5rem); font-weight: 700;
  letter-spacing: .02em; margin: 0; line-height: 1.1;
}
.headline .lock { color: var(--accent); }
.subline { color: var(--muted); font-size: .8rem; margin-top: .55rem; }
.subline b { color: var(--text); font-weight: 700; }

/* ---- stats ---- */
.stats {
  display: grid; grid-template-columns: repeat(4, 1fr);
  border: 1px solid var(--line); border-top: none; background: var(--panel);
}
.stat { padding: 1.05rem 1.2rem; border-left: 1px solid var(--line); }
.stat:first-child { border-left: none; }
.stat .n { font-size: 2rem; line-height: 1; font-weight: 700; color: var(--accent); }
.stat .l {
  font-size: .64rem; letter-spacing: .15em; text-transform: uppercase;
  color: var(--faint); margin-top: .45rem;
}

/* ---- toolbar ---- */
.toolbar { position: sticky; top: 0; z-index: 9; background: var(--bg); padding: .9rem 0 .5rem; }
.searchrow { display: flex; gap: .5rem; }
.search {
  flex: 1; display: flex; align-items: center;
  border: 1px solid var(--line); background: var(--panel);
}
.search:focus-within { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
.search .prompt { color: var(--accent); padding: 0 .1rem 0 .8rem; user-select: none; font-weight: 700; }
#filter {
  flex: 1; background: transparent; border: none; color: var(--text);
  font: inherit; padding: .68rem .7rem; outline: none;
}
#filter::placeholder { color: var(--faint); }
.btn {
  font: inherit; font-size: .72rem; letter-spacing: .06em; text-transform: uppercase;
  background: var(--panel); color: var(--muted); border: 1px solid var(--line);
  padding: 0 .9rem; cursor: pointer; white-space: nowrap;
}
.btn:hover { color: var(--accent); border-color: var(--accent); }
.countline { color: var(--faint); font-size: .72rem; margin: .55rem 0 .2rem; letter-spacing: .04em; }
.countline b { color: var(--muted); }

/* ---- project card ---- */
.repo {
  border: 1px solid var(--line); background: var(--panel); margin-top: -1px;
  animation: rise .4s ease both;
}
.repo.gone { display: none; }
.repo:hover { border-color: var(--line-2); position: relative; z-index: 1; }
@keyframes rise { from { opacity: 0; transform: translateY(7px); } to { opacity: 1; transform: none; } }
.repo-head {
  width: 100%; display: flex; align-items: center; gap: .6rem;
  background: none; border: none; color: inherit; font: inherit;
  cursor: pointer; padding: .8rem 1rem; text-align: left;
}
.repo-head:hover { background: var(--panel-2); }
.caret { color: var(--accent); transition: transform .16s ease; font-size: .8rem; }
.repo.open .caret { transform: rotate(90deg); }
.repo-name { font-weight: 700; font-size: .95rem; }
.repo-tags { display: flex; gap: .3rem; flex-wrap: wrap; }
.tag {
  font-size: .62rem; letter-spacing: .05em; text-transform: uppercase; color: var(--accent);
}
.tag::before { content: "["; opacity: .55; }
.tag::after { content: "]"; opacity: .55; }
.repo-count { margin-left: auto; color: var(--text); font-weight: 700; font-size: .95rem; }
.repo-count small { color: var(--faint); font-weight: 400; font-size: .62rem; margin-left: .25rem; letter-spacing: .08em; }

.repo-body { display: none; border-top: 1px solid var(--line); padding: .5rem 1rem 1rem; }
.repo.open .repo-body { display: block; }

/* ---- how-to ---- */
.howto { margin: .4rem 0 .2rem; }
.howto summary {
  cursor: pointer; list-style: none; user-select: none; width: fit-content;
  color: var(--muted); font-size: .73rem; letter-spacing: .04em; padding: .2rem 0;
}
.howto summary::-webkit-details-marker { display: none; }
.howto summary::before { content: "+ "; color: var(--accent); font-weight: 700; }
.howto[open] summary::before { content: "- "; }
.cmd-grp { display: flex; align-items: center; flex-wrap: wrap; gap: .35rem; margin: .35rem 0; }
.cmd-env {
  font-size: .62rem; text-transform: uppercase; letter-spacing: .07em;
  color: var(--faint); min-width: 5.5rem;
}
.cmd {
  display: flex; align-items: center; gap: .5rem; cursor: pointer; max-width: 100%;
  background: var(--panel-2); border: 1px solid var(--line); color: var(--text); font: inherit;
  padding: .34rem .55rem;
}
.cmd:hover { border-color: var(--accent); }
.cmd code { color: var(--muted); font-size: .73rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cmd-tag {
  font-size: .58rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: var(--bg); background: var(--accent); padding: .12rem .34rem;
}
.cmd-ico { color: var(--faint); font-size: .85rem; }
.cmd:hover .cmd-ico { color: var(--accent); }
.cmd.copied { border-color: var(--ok); }
.cmd.copied .cmd-tag { background: var(--ok); }
.cmd.copied .cmd-ico { color: var(--ok); }

/* ---- files + keys ---- */
.file { margin-top: .85rem; }
.file-head { display: flex; align-items: baseline; gap: .5rem; }
.file-path { color: var(--accent-2); font-size: .77rem; }
.file-n {
  font-size: .62rem; color: var(--faint); border: 1px solid var(--line);
  padding: 0 .35rem; letter-spacing: .04em;
}
.file-n::after { content: " keys"; }
.keys { display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .4rem; }
.keys code {
  font-size: .73rem; color: var(--text); background: var(--panel-2);
  border: 1px solid var(--line); padding: .15rem .45rem;
}
.keys code:hover { border-color: var(--line-2); color: var(--accent); }
.keys.empty { color: var(--danger); font-size: .76rem; }

.vault-empty { color: var(--muted); text-align: center; padding: 3rem; border: 1px dashed var(--line); }
#empty { display: none; color: var(--muted); text-align: center; padding: 2.5rem; border: 1px dashed var(--line); }

.foot {
  margin-top: 2.4rem; padding-top: 1.1rem; border-top: 1px solid var(--line);
  color: var(--faint); font-size: .72rem; line-height: 1.8;
}
.foot .safe { color: var(--ok); }
.foot code { color: var(--muted); background: var(--panel); border: 1px solid var(--line); padding: 0 .3rem; }

@media (max-width: 640px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .stat:nth-child(3) { border-left: none; }
  .stat:nth-child(n+3) { border-top: 1px solid var(--line); }
  .repo-count { margin-left: 0; }
  .cmd code { max-width: 56vw; }
}
@media (prefers-reduced-motion: reduce) { .repo { animation: none; } }
</style></head>
<body>
<div class="wrap">

  <div class="console">
    <div class="titlebar">
      <span class="brand">ENVSEAL</span>
      <span class="leader"></span>
      <button id="theme" type="button">&#9681; theme</button>
    </div>
    <h1 class="headline"><span class="lock">&#9919;</span> SECRETS OVERVIEW</h1>
    <div class="subline">
      <b>key names only</b> &mdash; no secret values are stored in this file &middot;
      generated __GENERATED__
    </div>
  </div>

  <div class="stats">
    <div class="stat"><div class="n">__REPOS__</div><div class="l">projects</div></div>
    <div class="stat"><div class="n">__KEYS__</div><div class="l">keys</div></div>
    <div class="stat"><div class="n">__FILES__</div><div class="l">env files</div></div>
    <div class="stat"><div class="n">__ENVS__</div><div class="l">environments</div></div>
  </div>

  <div class="toolbar">
    <div class="searchrow">
      <label class="search">
        <span class="prompt">&#47;</span>
        <input id="filter" type="search" autocomplete="off"
               placeholder="filter by project or key name...">
      </label>
      <button id="toggleAll" class="btn" type="button">expand all</button>
    </div>
    <div class="countline"><b id="count"></b></div>
  </div>

  __BODY__
  <p id="empty">// no project matches that filter</p>

  <div class="foot">
    <span class="safe">&#10003; safe to share</span> &mdash; this file contains key
    <em>names</em> only; decrypted secret values never touch it.<br>
    generated by <code>envseal report</code> &middot; retrieve a project with
    <code>envseal pull &lt;project&gt; --env &lt;env&gt; --replace</code>
  </div>
</div>

<script>
(function () {
  var root = document.documentElement;
  var saved = localStorage.getItem('envseal-theme');
  if (saved) root.setAttribute('data-theme', saved);
  else if (window.matchMedia('(prefers-color-scheme: light)').matches)
    root.setAttribute('data-theme', 'light');
  document.getElementById('theme').addEventListener('click', function () {
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem('envseal-theme', next);
  });

  var repos = Array.prototype.slice.call(document.querySelectorAll('.repo'));
  var filter = document.getElementById('filter');
  var empty = document.getElementById('empty');
  var count = document.getElementById('count');
  var toggleAll = document.getElementById('toggleAll');

  repos.forEach(function (r) {
    r.querySelector('.repo-head').addEventListener('click', function () {
      r.classList.toggle('open');
    });
  });

  function refresh() {
    var q = filter.value.trim().toLowerCase();
    var shown = 0;
    repos.forEach(function (r) {
      var match = !q || r.dataset.search.indexOf(q) !== -1;
      r.classList.toggle('gone', !match);
      if (match) {
        shown++;
        if (q) r.classList.add('open');
      }
    });
    empty.style.display = shown ? 'none' : 'block';
    count.textContent = q
      ? shown + ' / ' + repos.length + ' projects match'
      : repos.length + ' projects';
  }
  filter.addEventListener('input', refresh);
  refresh();

  var allOpen = false;
  toggleAll.addEventListener('click', function () {
    allOpen = !allOpen;
    repos.forEach(function (r) { r.classList.toggle('open', allOpen); });
    toggleAll.textContent = allOpen ? 'collapse all' : 'expand all';
  });

  document.querySelectorAll('.cmd').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var text = btn.getAttribute('data-copy');
      var flash = function () {
        var tag = btn.querySelector('.cmd-tag');
        var prev = tag.textContent;
        btn.classList.add('copied');
        tag.textContent = 'copied';
        setTimeout(function () {
          btn.classList.remove('copied');
          tag.textContent = prev;
        }, 1400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(flash, function () {});
      } else {
        var ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); flash(); } catch (e) {}
        document.body.removeChild(ta);
      }
    });
  });
})();
</script>
</body></html>
"""
    return (
        template.replace("__REPOS__", str(repo_count))
        .replace("__KEYS__", str(key_count))
        .replace("__FILES__", str(file_count))
        .replace("__ENVS__", str(env_count))
        .replace("__GENERATED__", esc(generated))
        .replace("__BODY__", body)
    )


def _load_config_and_sops() -> tuple[Config, "VaultManager", "SopsManager"]:
    """Shared setup for read-only commands: load config + age key, build managers."""
    config_path = Config.get_config_path()
    if not config_path.exists():
        console.print("[red]Config not found. Run 'envseal init' first.[/red]")
        raise typer.Exit(1)
    config = Config.load(config_path)

    key_manager = AgeKeyManager()
    key_path = key_manager.get_default_key_path()
    if not key_manager.key_exists(key_path):
        console.print("[red]Age key not found. Run 'envseal init' first.[/red]")
        raise typer.Exit(1)
    public_key = key_manager.get_public_key(key_path)

    vault_manager = VaultManager(config)
    sops = SopsManager(age_public_key=public_key, age_key_file=key_path)
    return config, vault_manager, sops


@app.command(name="list")
def list_secrets() -> None:
    """List every project's secrets in the vault (key names only, never values)."""
    config, vault_manager, sops = _load_config_and_sops()

    overview = _collect_overview(config, vault_manager, sops)
    if not overview:
        console.print("[yellow]No secrets in the vault yet.[/yellow]")
        return

    for repo_name in sorted(overview):
        console.print(f"\n[bold cyan]{repo_name}[/bold cyan]")
        for rel, keys in overview[repo_name]:
            console.print(f"  [green]{rel}[/green] [dim]({len(keys)} keys)[/dim]")
            if keys:
                console.print(f"    [dim]{', '.join(keys)}[/dim]")

    console.print("\n[dim]Key names only — secret values are never shown.[/dim]")


@app.command()
def report(
    output: Path = typer.Option(
        Path("envseal-report.html"),
        "--output",
        "-o",
        help="Where to write the HTML report",
    ),
) -> None:
    """Generate a static HTML overview of the vault (key names only, never values)."""
    config, vault_manager, sops = _load_config_and_sops()

    overview = _collect_overview(config, vault_manager, sops)
    output.write_text(_render_report_html(overview))
    console.print(f"✅ Report written to [cyan]{output}[/cyan]")
    console.print("[dim]Key names only — no secret values are in this file.[/dim]")


if __name__ == "__main__":
    app()
