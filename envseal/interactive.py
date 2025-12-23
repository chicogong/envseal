"""Interactive selection UI for envseal update command."""
import sys
from dataclasses import dataclass
from typing import Any, Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


@dataclass
class SelectionItem:
    """Item for interactive selection."""
    id: str  # Unique identifier (e.g., "repo_name/env_name")
    display: str  # Display text
    description: str  # Additional info
    data: Any  # Associated data
    selected: bool = False


class InteractiveSelector:
    """Interactive multi-select UI for terminal."""

    def __init__(self, items: list[SelectionItem], console: Optional[Console] = None):
        """Initialize the selector.

        Args:
            items: List of items to select from
            console: Rich console instance (optional)
        """
        self.items = items
        self.console = console or Console()
        self.cursor = 0
        self.cancelled = False

    def show(self) -> list[SelectionItem]:
        """Show selector and return selected items.

        Returns:
            List of selected items, or empty list if cancelled
        """
        if not self.items:
            return []

        # Check if running in interactive mode
        if not sys.stdin.isatty():
            self.console.print("[red]Interactive mode requires a TTY terminal[/red]")
            self.console.print("[yellow]Selecting all items by default...[/yellow]")
            # Select all items in non-interactive mode
            for item in self.items:
                item.selected = True
            return self.items

        # Show interactive selector
        with Live(self._render(), console=self.console, refresh_per_second=10) as live:
            while not self._handle_input(live):
                pass

        if self.cancelled:
            return []

        return [item for item in self.items if item.selected]

    def _render(self) -> Panel:
        """Render the current state of the selector."""
        table = Table(show_header=False, show_edge=False, box=None, padding=0)
        table.add_column("Selection", no_wrap=True)
        table.add_column("Item", no_wrap=False)

        for i, item in enumerate(self.items):
            # Selection indicator
            if i == self.cursor:
                selection = "[bold cyan]>[/bold cyan] "
            else:
                selection = "  "

            # Checkbox
            if item.selected:
                checkbox = "[green][X][/green]"
            else:
                checkbox = "[ ]"

            # Display text with description
            display = f"{item.display}"
            if item.description:
                display += f"\n    [dim]{item.description}[/dim]"

            # Add row with highlighting for cursor position
            if i == self.cursor:
                table.add_row(
                    f"{selection}{checkbox}",
                    f"[bold]{display}[/bold]"
                )
            else:
                table.add_row(f"{selection}{checkbox}", display)

        # Help text
        help_text = "\n[dim]↑↓/jk: navigate  Space: toggle  a: all  n: none  Enter: confirm  q/Esc: cancel[/dim]"

        return Panel(
            str(table) + help_text,
            title="[bold]Select items to update[/bold]",
            border_style="cyan"
        )

    def _handle_input(self, live: Live) -> bool:
        """Handle keyboard input.

        Returns:
            True if selection is complete, False to continue
        """
        key = self._get_key()

        if key in ['q', '\x1b']:  # q or Escape
            self.cancelled = True
            return True
        elif key == '\r':  # Enter
            return True
        elif key in ['\x1b[A', 'k']:  # Up arrow or k
            self.cursor = max(0, self.cursor - 1)
        elif key in ['\x1b[B', 'j']:  # Down arrow or j
            self.cursor = min(len(self.items) - 1, self.cursor + 1)
        elif key == ' ':  # Spacebar
            self.items[self.cursor].selected = not self.items[self.cursor].selected
        elif key == 'a':  # Select all
            for item in self.items:
                item.selected = True
        elif key == 'n':  # Select none
            for item in self.items:
                item.selected = False

        live.update(self._render())
        return False

    def _get_key(self) -> str:
        """Read a single key from stdin."""
        try:
            # Unix/Linux/macOS
            import tty
            import termios

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                key = sys.stdin.read(1)
                # Check for escape sequences
                if key == '\x1b':
                    key += sys.stdin.read(2)
                return key
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except ImportError:
            # Windows fallback
            import msvcrt
            key = msvcrt.getch().decode('utf-8', errors='ignore')
            return key