"""CLI surface for local-only secrets and Git leak prevention."""

from __future__ import annotations

import getpass
from pathlib import Path
from typing import NoReturn, Optional

import typer
from rich.console import Console

from envseal.broker import ENV_NAME, SecretBroker, validate_reference
from envseal.catalog import SecretCatalog
from envseal.config import Config
from envseal.guard import GitGuard, GuardError
from envseal.keychain import KeychainError, KeychainStore

console = Console()

secret_app = typer.Typer(help="Manage local secret references (values are never listed)")
guard_app = typer.Typer(help="Prevent secrets from entering Git history")


def _fail(message: object, exit_code: int = 1) -> NoReturn:
    """Render one consistent value-safe CLI error and exit."""
    console.print(f"[red]{message}[/red]")
    raise typer.Exit(exit_code)


@secret_app.command("put")
def secret_put(
    reference: str = typer.Argument(..., help="Reference such as project/prod/API_KEY"),
) -> None:
    """Prompt in macOS Keychain and store a persistent local secret."""
    store = KeychainStore()
    catalog = SecretCatalog()
    try:
        validate_reference(reference)
        console.print(f"Storing [cyan]{reference}[/cyan] in the local macOS Keychain...")
        store.put_interactive(reference)
    except (KeychainError, ValueError) as exc:
        _fail(exc)

    console.print(f"✅ Stored [cyan]{reference}[/cyan] in the local macOS Keychain")
    console.print("[dim]The value was not passed in argv and was not written by EnvSeal.[/dim]")
    try:
        catalog.record(reference)
    except (ValueError, OSError) as exc:
        _fail(f"Keychain write succeeded, but catalog update failed: {exc}")


@secret_app.command("list")
def secret_list(
    verify: bool = typer.Option(
        False,
        "--verify",
        help="Check whether each Keychain item exists without reading its value",
    ),
) -> None:
    """List value-free local references and optionally verify their presence."""
    catalog = SecretCatalog()
    try:
        items = catalog.list()
    except ValueError as exc:
        _fail(exc)
    if not items:
        console.print("[yellow]No local secret references recorded.[/yellow]")
        return

    store = KeychainStore()
    if verify and not store.available():
        _fail("Keychain verification is available only on macOS")
    missing = 0
    for item in items:
        state = ""
        if verify:
            present = store.contains(item.reference)
            state = " [green]present[/green]" if present else " [red]missing[/red]"
            missing += not present
        console.print(
            f"[cyan]{item.reference}[/cyan]  [dim]{item.backend} · {item.updated_at}[/dim]{state}"
        )
    console.print("\n[dim]Metadata only — values are never listed or read.[/dim]")
    if missing:
        console.print(
            f"[yellow]{missing} stale catalog entr{'y' if missing == 1 else 'ies'} detected. "
            "Remove each with: envseal secret remove <reference> --catalog-only[/yellow]"
        )


@secret_app.command("remove")
def secret_remove(
    reference: str = typer.Argument(..., help="Secret reference to remove"),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt"),
    catalog_only: bool = typer.Option(
        False,
        "--catalog-only",
        help="Remove stale metadata without changing the Keychain",
    ),
) -> None:
    """Remove a local Keychain item and its value-free catalog entry."""
    try:
        validate_reference(reference)
    except ValueError as exc:
        _fail(exc)
    target = "the local catalog" if catalog_only else "the local Keychain and catalog"
    if not yes and not typer.confirm(f"Remove {reference} from {target}?"):
        raise typer.Abort()
    if not catalog_only:
        try:
            KeychainStore().delete(reference)
        except KeychainError as exc:
            _fail(exc)

    try:
        SecretCatalog().remove(reference)
    except (ValueError, OSError) as exc:
        prefix = "Keychain removal succeeded, but " if not catalog_only else ""
        _fail(f"{prefix}catalog cleanup failed: {exc}")
    console.print(f"✅ Removed [cyan]{reference}[/cyan] from {target}")


def run(
    ctx: typer.Context,
    # Typer evaluates command annotations at runtime; Optional is required on
    # Python 3.9 even with ``from __future__ import annotations``.
    secret: Optional[list[str]] = typer.Option(  # noqa: UP045
        None,
        "--secret",
        "-s",
        help="Inject ENV_NAME=project/env/reference from Keychain (repeatable)",
    ),
    prompt: Optional[list[str]] = typer.Option(  # noqa: UP045
        None,
        "--prompt",
        "-p",
        help="Prompt for a temporary ENV_NAME held only for this command (repeatable)",
    ),
) -> None:
    """Run a trusted command with persistent or one-shot secrets injected."""
    command = list(ctx.args)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        _fail("A command is required after '--'.", exit_code=2)

    prompted: dict[str, str] = {}
    try:
        for name in prompt or []:
            if not ENV_NAME.fullmatch(name):
                raise ValueError(f"Invalid environment variable name: {name}")
            prompted[name] = getpass.getpass(f"Temporary value for {name}: ")
        exit_code = SecretBroker().run(command, secret or [], prompted)
    except (KeychainError, ValueError, OSError) as exc:
        _fail(exc)
    finally:
        prompted.clear()

    if exit_code:
        raise typer.Exit(128 + -exit_code if exit_code < 0 else exit_code)


@guard_app.command("staged")
def guard_staged(
    repo: Path = typer.Option(Path.cwd(), "--repo", help="Git working tree to scan"),
) -> None:
    """Scan staged changes with complete value redaction."""
    try:
        clean = GitGuard().scan_staged(repo.resolve())
    except GuardError as exc:
        _fail(exc, exit_code=2)
    if not clean:
        console.print("[red]Commit blocked: a possible secret was detected.[/red]")
        console.print("[yellow]Revoke/rotate it if it was ever committed or shared.[/yellow]")
        raise typer.Exit(1)
    console.print("✅ No secrets detected in staged changes")


@guard_app.command("install")
def guard_install(
    repo: Path = typer.Argument(Path.cwd(), help="Git working tree to protect"),
) -> None:
    """Install a pre-commit guard without overwriting an existing hook."""
    try:
        hook = GitGuard().install(repo.resolve())
    except GuardError as exc:
        _fail(exc)
    console.print(f"✅ Installed secret guard: [cyan]{hook}[/cyan]")


def doctor() -> None:
    """Check local secret-broker prerequisites without reading any values."""
    store = KeychainStore()
    catalog = SecretCatalog()
    guard = GitGuard()

    checks = [
        ("macOS Keychain client", store.available()),
        ("Gitleaks staged scanner", guard.available()),
        ("Private metadata permissions", catalog.permissions_are_private()),
    ]
    failed = False
    for label, ok in checks:
        marker = "✅" if ok else "❌"
        console.print(f"{marker} {label}")
        failed = failed or not ok

    config_path = Config.get_config_path()
    console.print(
        f"{'✅' if config_path.exists() else 'INFO'} Legacy SOPS config: "
        f"{config_path if config_path.exists() else 'not configured (optional)'}"
    )
    console.print("[dim]No Keychain values or decrypted vault files were read.[/dim]")
    if failed:
        raise typer.Exit(1)


def register_local_commands(app: typer.Typer) -> None:
    """Attach the local-only command surface to the root application."""
    app.add_typer(secret_app, name="secret")
    app.add_typer(guard_app, name="guard")
    app.command(
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )(run)
    app.command()(doctor)
