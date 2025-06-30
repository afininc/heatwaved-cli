import os
import shutil
from pathlib import Path

import oci
import typer
from oci.exceptions import ConfigFileNotFound, ServiceError
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from heatwaved.config.manager import ConfigManager

app = typer.Typer()
console = Console()


@app.callback(invoke_without_command=True)
def init(ctx: typer.Context):
    """Initialize HeatWave configuration with both database and OCI setup."""
    if ctx.invoked_subcommand is not None:
        return

    config_manager = ConfigManager()

    console.print("\n[bold cyan]HeatWave CLI Complete Setup[/bold cyan]\n")

    # Check if already initialized
    if config_manager.config_dir.exists() and not Confirm.ask(
        "[yellow]Configuration already exists. Overwrite?[/yellow]", default=False
    ):
        console.print("[red]Configuration cancelled.[/red]")
        raise typer.Exit()

    # Create configuration directory
    config_manager.ensure_config_dir()

    # Step 1: Database configuration
    _setup_database(config_manager)

    # Step 2: Ask if user wants to configure OCI
    console.print("\n" + "="*50 + "\n")
    if Confirm.ask(
        "[bold]Do you want to configure OCI authentication for Lakehouse POC?[/bold]",
        default=True
    ):
        _handle_oci_configuration(config_manager)
    else:
        console.print(
            "[dim]Skipping OCI configuration. "
            "You can set it up later with 'heatwaved init oci'[/dim]"
        )

    console.print("\n[bold green]✨ HeatWave CLI setup complete![/bold green]")
    console.print("\n[dim]Configuration saved to .heatwaved/[/dim]")


@app.command("db")
def init_db():
    """Initialize only database configuration."""
    config_manager = ConfigManager()

    # Create configuration directory if needed
    config_manager.ensure_config_dir()

    _setup_database(config_manager)
    console.print("\n[dim]Configuration saved to .heatwaved/[/dim]")


@app.command("oci")
def init_oci():
    """Initialize only OCI configuration."""
    config_manager = ConfigManager()

    # Check if base configuration exists
    if not config_manager.is_initialized():
        console.print(
            "[red]Error: HeatWave configuration not found. "
            "Please run 'heatwaved init db' first to set up database configuration.[/red]"
        )
        raise typer.Exit(1)

    _handle_oci_configuration(config_manager)


def _setup_database(config_manager: ConfigManager):
    """Setup database configuration and test connection."""
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

    # Save database configuration
    config_manager.save_db_config(db_config)
    console.print("\n[green]✓ Database configuration saved[/green]")

    # Test database connection
    console.print("\n[bold]Testing Database Connection...[/bold]")
    if _test_db_connection(db_config):
        console.print("\n[green]✓ Database connection successful![/green]")
    else:
        console.print(
            "\n[yellow]⚠ Configuration saved but database connection failed.[/yellow]"
        )
        console.print(
            "[dim]Please check your configuration and try 'heatwaved test --db'[/dim]"
        )


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

    # Test OCI authentication
    console.print("\n[bold]Testing OCI Authentication...[/bold]")
    if _test_oci_auth(config_manager):
        console.print(
            "\n[bold green]✨ OCI configuration added and verified successfully![/bold green]"
        )
    else:
        console.print(
            "\n[yellow]⚠ OCI configuration saved but authentication test failed.[/yellow]"
        )
        console.print("[dim]Please check your configuration and try 'heatwaved test --oci'[/dim]")


def _test_oci_auth(config_manager: ConfigManager) -> bool:
    """Test OCI authentication and return True if successful."""
    try:
        oci_config = config_manager.load_oci_config()
        if not oci_config or not oci_config.get('configured'):
            return False

        # Load OCI config
        config_path = oci_config['config_path']
        profile_name = oci_config.get('profile', 'DEFAULT')

        config = oci.config.from_file(
            file_location=config_path,
            profile_name=profile_name
        )

        # Validate the config
        oci.config.validate_config(config)

        # Test authentication by getting user info
        identity_client = oci.identity.IdentityClient(config)
        user = identity_client.get_user(config["user"]).data

        console.print(f"[green]✓ Authenticated as: {user.name}[/green]")
        console.print(f"[dim]  User OCID: {user.id[:50]}...[/dim]")

        # Get tenancy info
        tenancy = identity_client.get_tenancy(config["tenancy"]).data
        console.print(f"[dim]  Tenancy: {tenancy.name}[/dim]")
        console.print(f"[dim]  Region: {config.get('region', 'Not specified')}[/dim]")

        return True

    except ServiceError as e:
        console.print(f"[red]✗ OCI API error: {e.message}[/red]")
    except ConfigFileNotFound:
        console.print("[red]✗ Config file not found[/red]")
    except KeyError as e:
        console.print(f"[red]✗ Missing config parameter: {e}[/red]")
    except Exception as e:
        console.print(f"[red]✗ Authentication failed: {str(e)}[/red]")

    return False


def _test_db_connection(db_config: dict) -> bool:
    """Test database connection and return True if successful."""
    try:
        import mysql.connector

        console.print(f"Connecting to {db_config['host']}:{db_config['port']}...")

        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['username'],
            password=db_config['password'],
            connect_timeout=10  # 10 second timeout
        )

        if connection.is_connected():
            cursor = connection.cursor()

            # Get MySQL version
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            console.print(f"[green]✓ Connected to MySQL {version}[/green]")

            # Check if HeatWave is available
            cursor.execute("SHOW VARIABLES LIKE 'rapid_%'")
            heatwave_vars = cursor.fetchall()

            if heatwave_vars:
                console.print("[green]✓ HeatWave is available[/green]")
                console.print(f"[dim]  Found {len(heatwave_vars)} HeatWave variables[/dim]")
            else:
                console.print(
                    "[yellow]⚠ HeatWave not detected (no rapid_* variables found)[/yellow]"
                )

            # List available databases
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            console.print(f"[dim]  Available databases: {len(databases)}[/dim]")

            cursor.close()
            connection.close()
            return True

    except ImportError:
        console.print("[red]✗ mysql-connector-python not installed[/red]")
    except mysql.connector.Error as e:
        if "Access denied" in str(e):
            console.print("[red]✗ Authentication failed: Invalid username or password[/red]")
        elif "Can't connect" in str(e) or "not resolve" in str(e):
            console.print(
                f"[red]✗ Connection failed: Cannot reach "
                f"{db_config['host']}:{db_config['port']}[/red]"
            )
        else:
            console.print(f"[red]✗ Database error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]✗ Unexpected error: {str(e)}[/red]")

    return False
