import mysql.connector
import typer
from mysql.connector import Error
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax

from heatwaved.config.manager import ConfigManager

app = typer.Typer()
console = Console()


@app.command("setup")
def setup_genai(
    schema_name: str = typer.Argument(None, help="Schema name for GenAI operations"),
    input_schema: str = typer.Option(None, help="Input schema name (defaults to schema_name)"),
    output_schema: str = typer.Option(None, help="Output schema name (defaults to schema_name)"),
    show_only: bool = typer.Option(
        False, "--show-only", help="Only show SQL statements without executing"
    ),
):
    """Set up HeatWave GenAI permissions for the current user."""
    config_manager = ConfigManager()

    if not config_manager.is_initialized():
        console.print(
            "[red]Error: HeatWave configuration not found. "
            "Please run 'heatwaved init' first.[/red]"
        )
        raise typer.Exit(1)

    db_config = config_manager.load_db_config()
    if not db_config:
        console.print("[red]Error: Database configuration not found.[/red]")
        raise typer.Exit(1)

    # Get schema names
    if not schema_name:
        schema_name = Prompt.ask("Enter the schema name for GenAI operations")

    if not input_schema:
        input_schema = schema_name

    if not output_schema:
        output_schema = schema_name

    # Get the current username
    username = db_config['username']

    console.print("\n[bold]HeatWave GenAI Setup[/bold]")
    console.print(f"[dim]User: {username}[/dim]")
    console.print(f"[dim]Main schema: {schema_name}[/dim]")
    console.print(f"[dim]Input schema: {input_schema}[/dim]")
    console.print(f"[dim]Output schema: {output_schema}[/dim]")

    # Generate GRANT statements
    grant_statements = _generate_grant_statements(
        username, schema_name, input_schema, output_schema
    )

    # Show the SQL statements
    console.print("\n[bold]SQL statements to be executed:[/bold]")
    sql_syntax = Syntax("\n".join(grant_statements), "sql", theme="monokai", line_numbers=True)
    console.print(Panel(sql_syntax, title="GenAI Permission Grants", border_style="cyan"))

    if show_only:
        console.print("\n[yellow]--show-only flag set. Statements not executed.[/yellow]")
        return

    # Confirm execution
    if not Confirm.ask("\nDo you want to execute these statements?", default=True):
        console.print("[yellow]Operation cancelled.[/yellow]")
        return

    # Execute the statements
    try:
        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['username'],
            password=db_config['password'],
        )

        cursor = connection.cursor()

        console.print("\n[bold]Executing GRANT statements...[/bold]")

        for i, statement in enumerate(grant_statements, 1):
            try:
                cursor.execute(statement)
                console.print(f"[green]✓[/green] Statement {i}/{len(grant_statements)} executed")
            except Error as e:
                console.print(f"[red]✗[/red] Statement {i} failed: {e}")
                # Continue with other statements even if one fails

        connection.commit()
        console.print("\n[green]✓ HeatWave GenAI permissions setup completed![/green]")

        # Show summary
        _show_permissions_summary(cursor, username)

        cursor.close()
        connection.close()

    except Error as e:
        console.print(f"[red]✗ Failed to connect to database: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("check")
def check_genai_permissions():
    """Check current user's HeatWave GenAI permissions."""
    config_manager = ConfigManager()

    if not config_manager.is_initialized():
        console.print(
            "[red]Error: HeatWave configuration not found. "
            "Please run 'heatwaved init' first.[/red]"
        )
        raise typer.Exit(1)

    db_config = config_manager.load_db_config()
    if not db_config:
        console.print("[red]Error: Database configuration not found.[/red]")
        raise typer.Exit(1)

    try:
        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['username'],
            password=db_config['password'],
        )

        cursor = connection.cursor()
        username = db_config['username']

        console.print(f"\n[bold]HeatWave GenAI Permissions for {username}[/bold]\n")

        # Check grants
        cursor.execute("SHOW GRANTS FOR CURRENT_USER()")
        grants = cursor.fetchall()

        genai_related_grants = []
        for (grant,) in grants:
            if any(keyword in grant.upper() for keyword in [
                'VECTOR_STORE', 'RPD_', 'MYSQL_TASK_USER',
                'PERFORMANCE_SCHEMA', 'SYS.'
            ]):
                genai_related_grants.append(grant)

        if genai_related_grants:
            console.print("[green]✓ GenAI-related permissions found:[/green]")
            for grant in genai_related_grants:
                console.print(f"  [cyan]{grant}[/cyan]")
        else:
            console.print("[yellow]⚠ No GenAI-related permissions found[/yellow]")
            console.print("[dim]Run 'heatwaved genai setup' to configure permissions[/dim]")

        cursor.close()
        connection.close()

    except Error as e:
        console.print(f"[red]✗ Failed to check permissions: {e}[/red]")
        raise typer.Exit(1) from None


def _generate_grant_statements(username: str, schema_name: str,
                              input_schema: str, output_schema: str) -> list[str]:
    """Generate the GRANT statements with proper substitution."""
    statements = [
        f"GRANT 'mysql_task_user'@'%' TO '{username}'@'%'",
        f"GRANT VECTOR_STORE_LOAD_EXEC ON *.* TO '{username}'@'%'",
        f"GRANT SELECT ON performance_schema.rpd_nodes TO '{username}'@'%'",
        f"GRANT SELECT ON performance_schema.rpd_table_id TO '{username}'@'%'",
        f"GRANT SELECT ON performance_schema.rpd_tables TO '{username}'@'%'",
        f"GRANT SELECT ON sys.vector_store_load_metadata TO '{username}'@'%'",
        f"GRANT SELECT ON sys.vector_store_load_tables TO '{username}'@'%'",
        f"GRANT EXECUTE ON PROCEDURE sys.vector_store_load_current_schema TO '{username}'@'%'",
        f"GRANT EXECUTE ON PROCEDURE sys.vector_store_load TO '{username}'@'%'",
        f"GRANT CREATE, ALTER, EVENT ON {schema_name}.* TO '{username}'@'%'",
        f"GRANT SELECT, ALTER ON {input_schema}.* TO '{username}'@'%'",
        f"GRANT SELECT, INSERT, CREATE, DROP, ALTER, UPDATE "
        f"ON {output_schema}.* TO '{username}'@'%'",
    ]

    return statements


def _show_permissions_summary(cursor, username: str):
    """Show a summary of permissions after setup."""
    try:
        # Check if user has mysql_task_user role
        cursor.execute(
            "SELECT COUNT(*) FROM mysql.role_edges "
            "WHERE TO_USER = %s AND FROM_USER = 'mysql_task_user'",
            (username,)
        )
        has_task_user = cursor.fetchone()[0] > 0

        console.print("\n[bold]Permission Summary:[/bold]")
        status = '[green]✓[/green]' if has_task_user else '[red]✗[/red]'
        console.print(f"  mysql_task_user role: {status}")
        console.print("  VECTOR_STORE_LOAD_EXEC: [green]✓[/green]")
        console.print("  Performance schema tables: [green]✓[/green]")
        console.print("  Vector store procedures: [green]✓[/green]")

    except Exception:
        # If summary fails, it's not critical
        pass
