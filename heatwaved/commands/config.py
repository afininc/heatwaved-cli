
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from heatwaved.config.manager import ConfigManager

app = typer.Typer()
console = Console()


@app.command("show")
def show_config():
    """Show current HeatWave configuration."""
    config_manager = ConfigManager()

    if not config_manager.is_initialized():
        console.print(
            "[red]Error: HeatWave configuration not found. "
            "Please run 'heatwaved init' first.[/red]"
        )
        raise typer.Exit(1)

    console.print("\n[bold cyan]HeatWave Configuration[/bold cyan]\n")

    # Load and display database config
    db_config = config_manager.load_db_config()
    if db_config:
        table = Table(title="Database Configuration", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Host", db_config.get('host', 'Not set'))
        table.add_row("Port", str(db_config.get('port', 'Not set')))
        table.add_row("Username", db_config.get('username', 'Not set'))
        table.add_row("Password", "********" if db_config.get('password') else 'Not set')

        console.print(table)
    else:
        console.print("[yellow]No database configuration found[/yellow]")

    # Load and display OCI config
    console.print()
    oci_config = config_manager.load_oci_config()
    if oci_config and oci_config.get('configured'):
        oci_table = Table(title="OCI Configuration", show_header=True)
        oci_table.add_column("Setting", style="cyan")
        oci_table.add_column("Value", style="green")

        oci_table.add_row("Config Path", oci_config.get('config_path', 'Not set'))
        oci_table.add_row("Profile", oci_config.get('profile', 'Not set'))
        oci_table.add_row("Configured", "Yes" if oci_config.get('configured') else "No")

        console.print(oci_table)

        # Try to read and display OCI config details
        try:
            config_path = oci_config.get('config_path')
            if config_path and Path(config_path).exists():
                console.print(f"\n[dim]OCI Config File ({config_path}):[/dim]")
                with open(config_path) as f:
                    lines = f.readlines()
                    for line in lines:
                        if line.strip() and not line.strip().startswith('#'):
                            if 'key_file=' in line:
                                key, _ = line.strip().split('=', 1)
                                console.print(f"[dim]  {key}=<path_hidden>[/dim]")
                            elif any(s in line for s in ['fingerprint=', 'user=', 'tenancy=']):
                                key, value = line.strip().split('=', 1)
                                if len(value) > 20:
                                    masked_value = value[:10] + "..." + value[-10:]
                                else:
                                    masked_value = "***"
                                console.print(f"[dim]  {key}={masked_value}[/dim]")
                            else:
                                console.print(f"[dim]  {line.strip()}[/dim]")
        except Exception:
            pass
    else:
        console.print("[yellow]No OCI configuration found[/yellow]")

    console.print(f"\n[dim]Configuration directory: {config_manager.config_dir}[/dim]")


@app.command("path")
def show_config_path():
    """Show configuration directory path."""
    config_manager = ConfigManager()
    console.print(f"{config_manager.config_dir}")
