import os
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from heatwaved.config.manager import ConfigManager

app = typer.Typer()
console = Console()


@app.callback(invoke_without_command=True)
def init(
    ctx: typer.Context,
    oci: bool = typer.Option(False, "--oci", help="Configure OCI authentication for Lakehouse POC"),
):
    """Initialize HeatWave configuration in the current directory."""
    if ctx.invoked_subcommand is not None:
        return

    config_manager = ConfigManager()

    # If --oci flag is provided, only handle OCI configuration
    if oci:
        # Check if base configuration exists
        if not config_manager.is_initialized():
            console.print(
                "[red]Error: HeatWave configuration not found. "
                "Please run 'heatwaved init' first to set up database configuration.[/red]"
            )
            raise typer.Exit(1)

        _handle_oci_configuration(config_manager)
        return

    # Normal initialization (database configuration)
    console.print("\n[bold cyan]HeatWave CLI Configuration[/bold cyan]\n")

    # Check if already initialized
    if config_manager.config_dir.exists() and not Confirm.ask(
        "[yellow]Configuration already exists. Overwrite?[/yellow]", default=False
    ):
        console.print("[red]Configuration cancelled.[/red]")
        raise typer.Exit()

    # Create configuration directory
    config_manager.ensure_config_dir()

    # Database configuration
    console.print("[bold]Database Configuration[/bold]")

    db_host = Prompt.ask("DB Host")
    db_port = Prompt.ask("DB Port", default="3306")
    db_username = Prompt.ask("Username")
    db_password = Prompt.ask("Password", password=True)

    # Save database configuration
    db_config = {
        "host": db_host,
        "port": db_port,
        "username": db_username,
        "password": db_password,
    }

    config_manager.save_db_config(db_config)
    console.print("\n[green]✓ Database configuration saved[/green]")
    console.print("\n[bold green]✨ HeatWave CLI initialized successfully![/bold green]")
    console.print("\n[dim]Configuration saved to .heatwaved/[/dim]")


def _handle_oci_configuration(config_manager: ConfigManager):
    """Handle OCI configuration setup."""
    console.print("\n[bold]OCI Configuration[/bold]")
    console.print(
        Panel(
            "[yellow]To generate API keys, visit:[/yellow]\n"
            "https://cloud.oracle.com/identity/domains/my-profile/auth-tokens\n"
            "→ API keys → Add API key",
            title="OCI API Key Generation",
            border_style="yellow",
        )
    )

    console.print(
        "\n[dim]Paste your OCI configuration below (press Enter twice when done):[/dim]"
    )

    # Collect multi-line OCI config
    oci_config_lines = []
    empty_line_count = 0

    while True:
        line = input()
        if not line:
            empty_line_count += 1
            if empty_line_count >= 2:
                break
        else:
            empty_line_count = 0
            oci_config_lines.append(line)

    oci_config_text = "\n".join(oci_config_lines)

    # Parse OCI config
    oci_config = {}
    for line in oci_config_lines:
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            oci_config[key.strip()] = value.strip()

    # Handle key file
    if "key_file" in oci_config:
        console.print("\n[bold]Private Key File Configuration[/bold]")

        key_file_val = oci_config["key_file"]
        if "<path to your private keyfile>" in key_file_val or "TODO" in key_file_val:
            key_path = Prompt.ask(
                "Enter the path to your private key file",
                default="",
            )

            if key_path and os.path.exists(key_path):
                # Copy key file to .heatwaved/.oci/
                key_filename = Path(key_path).name
                dest_key_path = config_manager.oci_dir / key_filename
                shutil.copy2(key_path, dest_key_path)

                # Update key_file path in config
                oci_config["key_file"] = str(dest_key_path)
                console.print(f"[green]✓ Private key copied to {dest_key_path}[/green]")
            else:
                console.print(
                    "[yellow]⚠ Private key file not found. "
                    "You'll need to update this manually.[/yellow]"
                )
                oci_config["key_file"] = "<path to your private keyfile>"

    # Save OCI configuration
    config_manager.save_oci_config(oci_config_text, oci_config)
    console.print("\n[green]✓ OCI configuration saved[/green]")
    console.print("\n[bold green]✨ OCI configuration added successfully![/bold green]")
