"""Command-line interface for envseal."""

import typer
from typing import Optional
from envseal import __version__

app = typer.Typer(
    name="envseal",
    help="Manage encrypted .env files across multiple repositories",
    add_completion=False,
)


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


if __name__ == "__main__":
    app()
