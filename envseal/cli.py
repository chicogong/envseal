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
        return _html.escape(text, quote=True)

    repo_count = len(overview)
    key_count = sum(len(keys) for entries in overview.values() for _, keys in entries)
    file_count = sum(len(entries) for entries in overview.values())
    all_envs = {Path(rel).stem for entries in overview.values() for rel, _ in entries}
    env_count = len(all_envs)

    sections: list[str] = []
    for repo_name in sorted(overview, key=str.lower):
        files = overview[repo_name]
        total = sum(len(keys) for _, keys in files)
        safe = esc(repo_name)
        envs = sorted({Path(rel).stem for rel, _ in files})

        env_badges = "".join(f'<span class="env">{esc(e)}</span>' for e in envs)
        head = (
            f'<header class="repo-head">'
            f"<h2>{safe}</h2>"
            f'<div class="repo-meta">{env_badges}'
            f'<span class="kcount">{total} keys</span></div>'
            f"</header>"
        )

        cmd_rows: list[str] = []
        for e in envs:
            restore = f"envseal pull {repo_name} --env {e} --replace"
            copy = f"envseal pull {repo_name} --env {e} --stdout > {repo_name}-{e}.env"
            cmd_rows.append(
                f'<div class="cmd-row"><span class="cmd-env">{esc(e)}</span>'
                f'<button class="cmd" data-copy="{esc(restore)}" '
                f'title="Copy — restore into the project directory">'
                f'<span class="cmd-label">restore</span>'
                f"<code>{esc(restore)}</code></button>"
                f'<button class="cmd" data-copy="{esc(copy)}" '
                f'title="Copy — write a standalone copy">'
                f'<span class="cmd-label">copy</span>'
                f"<code>{esc(copy)}</code></button></div>"
            )
        howto = f'<details class="howto"><summary>How to retrieve</summary>{"".join(cmd_rows)}</details>'

        file_blocks: list[str] = []
        for rel, keys in files:
            if keys:
                tags = "".join(f"<code>{esc(k)}</code>" for k in keys)
                body_html = f'<div class="keys">{tags}</div>'
            else:
                body_html = '<div class="keys empty">could not read this file</div>'
            file_blocks.append(
                f'<div class="file"><div class="file-name">{esc(rel)}'
                f'<span class="file-count">{len(keys)}</span></div>{body_html}</div>'
            )

        sections.append(
            f'<section class="repo" data-name="{esc(repo_name.lower())}">'
            f"{head}{howto}{''.join(file_blocks)}</section>"
        )
    body = (
        "\n".join(sections)
        if sections
        else '<p class="vault-empty">No secrets in the vault yet.</p>'
    )
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EnvSeal — secrets overview</title>
<style>
:root {
  --bg: #f4f5f7; --panel: #ffffff; --panel-2: #f7f8fa; --border: #e4e6ea;
  --text: #1d1d1f; --muted: #6b7280; --faint: #9aa0a8;
  --accent: #6366f1; --accent-soft: #eef0ff; --accent-text: #4f46e5;
  --chip-bg: #f1f2f4; --chip-text: #374151;
  --ok: #16a34a; --danger: #dc2626;
  --shadow: 0 1px 2px rgba(16,24,40,.06), 0 8px 24px rgba(16,24,40,.06);
}
[data-theme="dark"] {
  --bg: #0d0f13; --panel: #15181e; --panel-2: #1b1f27; --border: #272b34;
  --text: #e6e8eb; --muted: #9aa0aa; --faint: #6b7280;
  --accent: #818cf8; --accent-soft: #1e2235; --accent-text: #a5b4fc;
  --chip-bg: #232730; --chip-text: #c7ccd4;
  --ok: #4ade80; --danger: #f87171;
  --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35);
}
* { box-sizing: border-box; }
body {
  font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  margin: 0; background: var(--bg); color: var(--text);
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 940px; margin: 0 auto; padding: 0 1.1rem 4rem; }
code, .mono { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace; }

/* hero */
.hero {
  background: linear-gradient(135deg, var(--accent) 0%, #8b5cf6 100%);
  color: #fff; padding: 2.4rem 0 2rem;
}
.hero .wrap { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; padding-bottom: 0; }
.hero h1 { font-size: 1.6rem; margin: 0; font-weight: 650; letter-spacing: -.01em; }
.hero p { margin: .35rem 0 0; opacity: .85; font-size: .9rem; }
#theme {
  background: rgba(255,255,255,.16); color: #fff; border: 1px solid rgba(255,255,255,.28);
  border-radius: 8px; padding: .4rem .7rem; cursor: pointer; font-size: .85rem;
}
#theme:hover { background: rgba(255,255,255,.26); }

/* stats */
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: .8rem; margin: -1.5rem 0 1.6rem; }
.stat {
  background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
  padding: .9rem 1rem; box-shadow: var(--shadow);
}
.stat .num { font-size: 1.55rem; font-weight: 680; letter-spacing: -.02em; }
.stat .lbl { font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin-top: .1rem; }

/* toolbar */
.toolbar { position: sticky; top: 0; z-index: 5; background: var(--bg); padding: .7rem 0; margin-bottom: .4rem; }
.search { position: relative; }
.search svg { position: absolute; left: .8rem; top: 50%; transform: translateY(-50%); color: var(--faint); }
#filter {
  width: 100%; padding: .7rem .8rem .7rem 2.3rem; font-size: .95rem;
  border: 1px solid var(--border); border-radius: 10px; background: var(--panel); color: var(--text);
  box-shadow: var(--shadow);
}
#filter:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
#empty { color: var(--muted); display: none; padding: 1.5rem; text-align: center; }
.vault-empty { color: var(--muted); padding: 2rem; text-align: center; }

/* project card */
.repo {
  background: var(--panel); border: 1px solid var(--border); border-radius: 14px;
  padding: 1.1rem 1.2rem; margin-bottom: .9rem; box-shadow: var(--shadow);
}
.repo.hidden { display: none; }
.repo-head { display: flex; align-items: center; justify-content: space-between; gap: .8rem; flex-wrap: wrap; }
.repo-head h2 { font-size: 1.08rem; margin: 0; font-weight: 620; letter-spacing: -.01em; }
.repo-meta { display: flex; align-items: center; gap: .35rem; flex-wrap: wrap; }
.env {
  font-size: .68rem; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
  background: var(--accent-soft); color: var(--accent-text); border-radius: 5px; padding: .12rem .42rem;
}
.kcount { font-size: .78rem; color: var(--muted); background: var(--chip-bg); border-radius: 20px; padding: .14rem .6rem; }

/* how-to */
.howto { margin: .85rem 0 .2rem; }
.howto summary {
  cursor: pointer; font-size: .78rem; color: var(--accent-text); font-weight: 550;
  list-style: none; user-select: none; width: fit-content;
}
.howto summary::before { content: "▸ "; }
.howto[open] summary::before { content: "▾ "; }
.cmd-row { display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; margin: .5rem 0; }
.cmd-env {
  font-size: .68rem; font-weight: 600; text-transform: uppercase;
  color: var(--muted); min-width: 3.4rem;
}
.cmd {
  display: inline-flex; align-items: center; gap: .4rem; cursor: pointer;
  background: var(--panel-2); border: 1px solid var(--border); border-radius: 7px;
  padding: .3rem .55rem; font-size: .76rem; color: var(--text); max-width: 100%;
}
.cmd:hover { border-color: var(--accent); }
.cmd code { color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cmd-label {
  font-size: .64rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
  color: var(--accent-text); background: var(--accent-soft); border-radius: 4px; padding: .1rem .35rem;
}
.cmd.copied { border-color: var(--ok); }
.cmd.copied .cmd-label { color: var(--ok); background: transparent; }

/* files + keys */
.file { margin-top: .85rem; }
.file-name {
  font-size: .8rem; color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  display: flex; align-items: center; gap: .45rem; margin-bottom: .35rem;
}
.file-count {
  font-size: .68rem; background: var(--chip-bg); color: var(--chip-text);
  border-radius: 20px; padding: .04rem .42rem;
}
.keys { display: flex; flex-wrap: wrap; gap: .3rem; }
.keys code {
  background: var(--chip-bg); color: var(--chip-text); border-radius: 6px;
  padding: .16rem .46rem; font-size: .76rem;
}
.keys.empty { color: var(--danger); font-size: .8rem; font-style: italic; }

.note { color: var(--faint); font-size: .78rem; margin-top: 2rem; text-align: center; }
.note code { background: var(--chip-bg); border-radius: 4px; padding: .05rem .35rem; }

@media (max-width: 620px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .cmd code { max-width: 60vw; }
}
</style></head>
<body>
<div class="hero">
  <div class="wrap">
    <div>
      <h1>&#128272; EnvSeal</h1>
      <p>Secrets overview &middot; key names only &middot; generated __GENERATED__</p>
    </div>
    <button id="theme" type="button">&#9789; Theme</button>
  </div>
</div>
<div class="wrap">
  <div class="stats">
    <div class="stat"><div class="num">__REPOS__</div><div class="lbl">Projects</div></div>
    <div class="stat"><div class="num">__KEYS__</div><div class="lbl">Keys</div></div>
    <div class="stat"><div class="num">__FILES__</div><div class="lbl">Env files</div></div>
    <div class="stat"><div class="num">__ENVS__</div><div class="lbl">Environments</div></div>
  </div>
  <div class="toolbar">
    <div class="search">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg>
      <input id="filter" type="search" placeholder="Filter projects by name…" autocomplete="off">
    </div>
  </div>
  <p id="empty">No project matches that filter.</p>
  __BODY__
  <p class="note">Key names only — no secret values appear in this file. Safe to share.<br>Generated by <code>envseal report</code>.</p>
</div>
<script>
(function () {
  var root = document.documentElement;
  var saved = localStorage.getItem('envseal-theme');
  var dark = saved ? saved === 'dark'
    : window.matchMedia('(prefers-color-scheme: dark)').matches;
  root.setAttribute('data-theme', dark ? 'dark' : 'light');
  document.getElementById('theme').addEventListener('click', function () {
    dark = !dark;
    root.setAttribute('data-theme', dark ? 'dark' : 'light');
    localStorage.setItem('envseal-theme', dark ? 'dark' : 'light');
  });

  var f = document.getElementById('filter');
  var repos = Array.prototype.slice.call(document.querySelectorAll('.repo'));
  var empty = document.getElementById('empty');
  f.addEventListener('input', function () {
    var q = f.value.trim().toLowerCase();
    var shown = 0;
    repos.forEach(function (r) {
      var match = r.dataset.name.indexOf(q) !== -1;
      r.classList.toggle('hidden', !match);
      if (match) shown++;
    });
    empty.style.display = shown ? 'none' : 'block';
  });

  document.querySelectorAll('.cmd').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var text = btn.getAttribute('data-copy');
      var done = function () {
        var label = btn.querySelector('.cmd-label');
        var prev = label.textContent;
        btn.classList.add('copied');
        label.textContent = 'copied';
        setTimeout(function () {
          btn.classList.remove('copied');
          label.textContent = prev;
        }, 1400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () {});
      } else {
        var ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); done(); } catch (e) {}
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
