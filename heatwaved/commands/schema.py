import mysql.connector
import typer
from mysql.connector import Error
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from heatwaved.config.manager import ConfigManager

app = typer.Typer()
console = Console()


@app.command("create")
def create_schema(
    name: str = typer.Argument(..., help="Name of the schema to create"),
    charset: str = typer.Option("utf8mb4", help="Character set for the schema"),
    collation: str = typer.Option("utf8mb4_0900_ai_ci", help="Collation for the schema"),
    if_not_exists: bool = typer.Option(True, help="Add IF NOT EXISTS clause"),
):
    """Create a new schema (database) in MySQL HeatWave."""
    config_manager = ConfigManager()

    if not config_manager.is_initialized():
        console.print(
            "[red]Error: HeatWave configuration not found. "
            "Please run 'heatwaved init' first.[/red]"
        )
        raise typer.Exit(1) from None

    db_config = config_manager.load_db_config()
    if not db_config:
        console.print("[red]Error: Database configuration not found.[/red]")
        raise typer.Exit(1) from None

    # Validate schema name
    if not _validate_schema_name(name):
        console.print(f"[red]Error: Invalid schema name '{name}'.[/red]")
        console.print(
            "[dim]Schema names must start with a letter and contain "
            "only letters, numbers, and underscores.[/dim]"
        )
        raise typer.Exit(1) from None

    console.print(f"\n[bold]Creating schema: {name}[/bold]")
    console.print(f"[dim]Character set: {charset}[/dim]")
    console.print(f"[dim]Collation: {collation}[/dim]")

    try:
        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['username'],
            password=db_config['password'],
        )

        cursor = connection.cursor()

        # Build CREATE SCHEMA statement
        if_not_exists_clause = "IF NOT EXISTS " if if_not_exists else ""
        create_stmt = (
            f"CREATE SCHEMA {if_not_exists_clause}{name} "
            f"DEFAULT CHARACTER SET {charset} "
            f"DEFAULT COLLATE {collation}"
        )

        cursor.execute(create_stmt)
        connection.commit()

        console.print(f"\n[green]✓ Schema '{name}' created successfully![/green]")

        # Show the created schema
        cursor.execute(f"SHOW CREATE SCHEMA {name}")
        result = cursor.fetchone()
        if result:
            console.print("\n[dim]Schema definition:[/dim]")
            console.print(f"[cyan]{result[1]}[/cyan]")

        cursor.close()
        connection.close()

    except Error as e:
        if "database exists" in str(e).lower():
            console.print(f"[yellow]⚠ Schema '{name}' already exists.[/yellow]")
        else:
            console.print(f"[red]✗ Failed to create schema: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("list")
def list_schemas(
    pattern: str = typer.Option(None, help="Filter schemas by pattern (supports % wildcard)"),
):
    """List all schemas (databases) in MySQL HeatWave."""
    config_manager = ConfigManager()

    if not config_manager.is_initialized():
        console.print(
            "[red]Error: HeatWave configuration not found. "
            "Please run 'heatwaved init' first.[/red]"
        )
        raise typer.Exit(1) from None

    db_config = config_manager.load_db_config()
    if not db_config:
        console.print("[red]Error: Database configuration not found.[/red]")
        raise typer.Exit(1) from None

    try:
        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['username'],
            password=db_config['password'],
        )

        cursor = connection.cursor()

        # Get schemas
        if pattern:
            cursor.execute("SHOW DATABASES LIKE %s", (pattern,))
        else:
            cursor.execute("SHOW DATABASES")

        schemas = cursor.fetchall()

        if not schemas:
            console.print("[yellow]No schemas found.[/yellow]")
            return

        # Create table
        table = Table(title="Available Schemas", show_header=True)
        table.add_column("Schema Name", style="cyan")

        # Get additional info for each schema
        for (schema_name,) in schemas:
            # Skip system schemas unless explicitly requested
            if schema_name in ['information_schema', 'mysql', 'performance_schema', 'sys']:
                if not pattern or pattern == '%':
                    continue

            table.add_row(schema_name)

        console.print(table)
        console.print(f"\n[dim]Total schemas: {len(schemas)}[/dim]")

        cursor.close()
        connection.close()

    except Error as e:
        console.print(f"[red]✗ Failed to list schemas: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("drop")
def drop_schema(
    name: str = typer.Argument(..., help="Name of the schema to drop"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Drop a schema (database) from MySQL HeatWave."""
    config_manager = ConfigManager()

    if not config_manager.is_initialized():
        console.print(
            "[red]Error: HeatWave configuration not found. "
            "Please run 'heatwaved init' first.[/red]"
        )
        raise typer.Exit(1) from None

    db_config = config_manager.load_db_config()
    if not db_config:
        console.print("[red]Error: Database configuration not found.[/red]")
        raise typer.Exit(1) from None

    # Protect system schemas
    protected_schemas = ['information_schema', 'mysql', 'performance_schema', 'sys']
    if name.lower() in protected_schemas:
        console.print(f"[red]Error: Cannot drop system schema '{name}'.[/red]")
        raise typer.Exit(1) from None

    # Confirm before dropping
    if not force:
        console.print(
            f"\n[bold red]WARNING: This will permanently delete schema '{name}'![/bold red]"
        )
        if not Confirm.ask(f"Are you sure you want to drop schema '{name}'?", default=False):
            console.print("[yellow]Operation cancelled.[/yellow]")
            raise typer.Exit()

    try:
        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['username'],
            password=db_config['password'],
        )

        cursor = connection.cursor()

        # Drop the schema
        cursor.execute(f"DROP SCHEMA IF EXISTS {name}")
        connection.commit()

        console.print(f"\n[green]✓ Schema '{name}' dropped successfully![/green]")

        cursor.close()
        connection.close()

    except Error as e:
        console.print(f"[red]✗ Failed to drop schema: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("use")
def use_schema(
    name: str = typer.Argument(..., help="Name of the schema to use as default"),
):
    """Set a default schema for future operations."""
    config_manager = ConfigManager()

    if not config_manager.is_initialized():
        console.print(
            "[red]Error: HeatWave configuration not found. "
            "Please run 'heatwaved init' first.[/red]"
        )
        raise typer.Exit(1) from None

    db_config = config_manager.load_db_config()
    if not db_config:
        console.print("[red]Error: Database configuration not found.[/red]")
        raise typer.Exit(1) from None

    # Test connection with the specified schema
    try:
        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['username'],
            password=db_config['password'],
            database=name  # Try to use the schema
        )

        console.print(f"\n[green]✓ Successfully connected to schema '{name}'![/green]")

        # Update configuration with default schema
        db_config['database'] = name
        config_manager.save_db_config(db_config)

        console.print(f"[green]✓ Default schema set to '{name}'[/green]")

        connection.close()

    except Error as e:
        if "Unknown database" in str(e):
            console.print(f"[red]✗ Schema '{name}' does not exist.[/red]")
        else:
            console.print(f"[red]✗ Failed to use schema: {e}[/red]")
        raise typer.Exit(1) from None


def _validate_schema_name(name: str) -> bool:
    """Validate schema name according to MySQL rules."""
    import re
    # MySQL schema names: start with letter, contain letters, numbers, underscore
    # Max length 64 characters
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]{0,63}$'
    return bool(re.match(pattern, name))
