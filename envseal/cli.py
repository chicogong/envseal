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

    repo_count = len(overview)
    key_count = sum(len(keys) for entries in overview.values() for _, keys in entries)

    sections: list[str] = []
    for repo_name in sorted(overview):
        files = overview[repo_name]
        total = sum(len(keys) for _, keys in files)
        safe = _html.escape(repo_name)
        rows = [f'<h2 id="{safe}">{safe} <span class="count">{total} keys</span></h2>']
        for rel, keys in files:
            rows.append(f'<div class="file">{_html.escape(rel)}</div>')
            if keys:
                tags = " ".join(f"<code>{_html.escape(k)}</code>" for k in keys)
                rows.append(f'<div class="keys">{tags}</div>')
            else:
                rows.append('<div class="keys empty">(could not read)</div>')
        sections.append(
            f'<section class="repo" data-name="{safe.lower()}">' + "\n".join(rows) + "</section>"
        )
    body = "\n".join(sections) if sections else "<p>No secrets in the vault yet.</p>"

    template = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>EnvSeal - secrets overview</title>
<style>
body { font: 15px/1.6 -apple-system, system-ui, sans-serif; max-width: 820px; margin: 2rem auto; padding: 0 1rem; color: #1d1d1f; }
h1 { font-size: 1.4rem; margin-bottom: .2rem; }
.summary { color: #555; font-size: .9rem; margin: 0 0 1rem; }
#filter { width: 100%; box-sizing: border-box; padding: .5rem .7rem; font-size: .95rem; border: 1px solid #ccc; border-radius: 6px; margin-bottom: .5rem; }
h2 { font-size: 1.05rem; margin: 1.6rem 0 .3rem; border-bottom: 1px solid #eee; padding-bottom: .2rem; }
.count { color: #888; font-weight: normal; font-size: .85rem; }
.file { color: #555; font-size: .85rem; margin: .6rem 0 .25rem; }
.keys code { background: #f3f3f5; border-radius: 4px; padding: 1px 6px; margin: 2px; display: inline-block; font-size: .8rem; }
.keys.empty { color: #c00; font-size: .8rem; }
.repo.hidden { display: none; }
#empty { color: #888; display: none; }
.note { color: #888; font-size: .8rem; margin-top: 2rem; }
</style></head>
<body>
<h1>&#128272; EnvSeal - secrets overview</h1>
<p class="summary"><strong>__REPOS__</strong> projects &middot; <strong>__KEYS__</strong> keys &middot; key names only</p>
<input id="filter" type="search" placeholder="Filter projects by name...">
<p id="empty">No project matches that filter.</p>
__BODY__
<p class="note">Key names only - no secret values appear in this file. Safe to share. Generated by <code>envseal report</code>.</p>
<script>
const f = document.getElementById('filter');
const repos = Array.from(document.querySelectorAll('.repo'));
const empty = document.getElementById('empty');
f.addEventListener('input', function () {
  const q = f.value.trim().toLowerCase();
  let shown = 0;
  repos.forEach(function (r) {
    const match = r.dataset.name.indexOf(q) !== -1;
    r.classList.toggle('hidden', !match);
    if (match) shown++;
  });
  empty.style.display = shown ? 'none' : 'block';
});
</script>
</body></html>
"""
    return (
        template.replace("__REPOS__", str(repo_count))
        .replace("__KEYS__", str(key_count))
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
