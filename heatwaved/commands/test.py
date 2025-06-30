
import oci
import typer
from oci.exceptions import ConfigFileNotFound, ServiceError
from rich.console import Console

from heatwaved.config.manager import ConfigManager

app = typer.Typer()
console = Console()


@app.callback(invoke_without_command=True)
def test_connection(
    ctx: typer.Context,
    oci_only: bool = typer.Option(False, "--oci", help="Test only OCI authentication"),
    db_only: bool = typer.Option(False, "--db", help="Test only database connection"),
):
    """Test HeatWave and OCI connections."""
    if ctx.invoked_subcommand is not None:
        return

    config_manager = ConfigManager()

    if not config_manager.is_initialized():
        console.print(
            "[red]Error: HeatWave configuration not found. "
            "Please run 'heatwaved init' first.[/red]"
        )
        raise typer.Exit(1)

    # Determine what to test
    test_oci = True
    test_db = True

    if oci_only:
        test_db = False
    elif db_only:
        test_oci = False

    # Test database connection
    if test_db:
        _test_database_connection(config_manager)

    # Test OCI authentication
    if test_oci:
        _test_oci_authentication(config_manager)


def _test_database_connection(config_manager: ConfigManager):
    """Test database connection."""
    console.print("\n[bold]Testing Database Connection[/bold]")

    db_config = config_manager.load_db_config()
    if not db_config:
        console.print("[yellow]⚠ Database configuration not found[/yellow]")
        return

    try:
        import mysql.connector

        console.print(f"Connecting to {db_config['host']}:{db_config['port']}...")

        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['username'],
            password=db_config['password'],
        )

        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]

            console.print("[green]✓ Successfully connected to MySQL[/green]")
            console.print(f"[dim]  MySQL Version: {version}[/dim]")

            # Check if HeatWave is available
            cursor.execute("SHOW VARIABLES LIKE 'rapid_%'")
            heatwave_vars = cursor.fetchall()

            if heatwave_vars:
                console.print("[green]✓ HeatWave is available[/green]")
                for var_name, var_value in heatwave_vars[:3]:  # Show first 3 variables
                    console.print(f"[dim]  {var_name}: {var_value}[/dim]")
            else:
                console.print("[yellow]⚠ HeatWave variables not found[/yellow]")

            cursor.close()
            connection.close()

    except mysql.connector.Error as e:
        console.print(f"[red]✗ Database connection failed: {e}[/red]")
    except ImportError:
        console.print("[red]✗ mysql-connector-python not installed[/red]")


def _test_oci_authentication(config_manager: ConfigManager):
    """Test OCI authentication."""
    console.print("\n[bold]Testing OCI Authentication[/bold]")

    oci_config = config_manager.load_oci_config()
    if not oci_config or not oci_config.get('configured'):
        console.print(
            "[yellow]⚠ OCI configuration not found. "
            "Run 'heatwaved init --oci' to configure.[/yellow]"
        )
        return

    try:
        # Load OCI config
        config_path = oci_config['config_path']
        profile_name = oci_config.get('profile', 'DEFAULT')

        console.print(f"Loading OCI config from {config_path}...")

        config = oci.config.from_file(
            file_location=config_path,
            profile_name=profile_name
        )

        # Validate the config
        oci.config.validate_config(config)
        console.print("[green]✓ OCI configuration is valid[/green]")

        # Test authentication by getting user info
        identity_client = oci.identity.IdentityClient(config)

        try:
            user = identity_client.get_user(config["user"]).data
            console.print("[green]✓ OCI authentication successful[/green]")
            console.print(f"[dim]  User: {user.name}[/dim]")
            console.print(f"[dim]  OCID: {user.id}[/dim]")

            # Get tenancy info
            tenancy = identity_client.get_tenancy(config["tenancy"]).data
            console.print(f"[dim]  Tenancy: {tenancy.name}[/dim]")

            # List compartments (first 5)
            compartments = identity_client.list_compartments(
                config["tenancy"],
                limit=5
            ).data

            if compartments:
                console.print("\n[green]✓ Compartments accessible:[/green]")
                for comp in compartments[:3]:
                    console.print(f"[dim]  - {comp.name}[/dim]")
                if len(compartments) > 3:
                    console.print(f"[dim]  ... and {len(compartments) - 3} more[/dim]")

        except ServiceError as e:
            console.print(f"[red]✗ OCI API call failed: {e.message}[/red]")

    except ConfigFileNotFound:
        console.print(f"[red]✗ OCI config file not found at {config_path}[/red]")
    except KeyError as e:
        console.print(f"[red]✗ Missing required OCI config parameter: {e}[/red]")
    except Exception as e:
        console.print(f"[red]✗ OCI authentication failed: {str(e)}[/red]")
        console.print("[dim]  Check your OCI configuration and private key file[/dim]")
