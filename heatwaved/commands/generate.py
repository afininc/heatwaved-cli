import json

import mysql.connector
import typer
from mysql.connector import Error
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

from heatwaved.config.manager import ConfigManager

app = typer.Typer()
console = Console()


@app.command("text")
def generate_text(
    query: str = typer.Argument(
        "Write an article on Artificial intelligence in 200 words.",
        help="Natural language query for text generation"
    ),
    model: str = typer.Option(None, "--model", "-m", help="Model ID to use for generation"),
    language: str = typer.Option("en", "--lang", "-l", help="Language code (e.g., en, ko, fr)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode"),
    show_query: bool = typer.Option(
        False, "--show-query", help="Show the SQL query being executed"
    ),
):
    """Generate text-based content using HeatWave GenAI."""
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
        # Connect to database
        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['username'],
            password=db_config['password'],
            database=db_config.get('database'),
        )
        cursor = connection.cursor()

        # Ensure we have a database selected
        if 'database' in db_config and db_config['database']:
            cursor.execute(f"USE {db_config['database']}")
            console.print(f"[dim]Using database: {db_config['database']}[/dim]")

        # If no model specified, list available models and let user choose
        if not model:
            model = _select_model(cursor)
            if not model:
                console.print("[red]No model selected.[/red]")
                raise typer.Exit(1)

        # Interactive mode or single query mode
        if interactive:
            console.print("\n[bold cyan]HeatWave GenAI Interactive Mode[/bold cyan]")
            console.print("[dim]Type 'exit' or 'quit' to end the session[/dim]\n")

            while True:
                query = Prompt.ask("\n[bold]Query[/bold]")
                if query.lower() in ['exit', 'quit']:
                    break

                _generate_text(cursor, query, model, language, show_query)
        else:
            # Single query mode
            _generate_text(cursor, query, model, language, show_query)

        cursor.close()
        connection.close()

    except Error as e:
        console.print(f"[red]✗ Database error: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("batch")
def generate_batch(
    input_table: str = typer.Argument(..., help="Table.Column containing input queries"),
    output_table: str = typer.Argument(
        ..., help="Table.Column for output (table will be created if needed)"
    ),
    model: str = typer.Option(None, "--model", "-m", help="Model ID to use for generation"),
    language: str = typer.Option("en", "--lang", "-l", help="Language code (e.g., en, ko, fr)"),
    database: str = typer.Option(
        None, "--database", "-d", help="Database name (uses default if not specified)"
    ),
    show_query: bool = typer.Option(
        False, "--show-query", help="Show the SQL query being executed"
    ),
):
    """Run batch text generation queries using ML_GENERATE_TABLE."""
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

    # Use provided database or default from config
    if database:
        db_config['database'] = database
    elif 'database' not in db_config:
        console.print(
            "[red]Error: No database specified. "
            "Use --database or set a default with 'heatwaved schema use'[/red]"
        )
        raise typer.Exit(1)

    try:
        # Connect to database
        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['username'],
            password=db_config['password'],
            database=db_config.get('database'),
        )
        cursor = connection.cursor()

        # If no model specified, list available models and let user choose
        if not model:
            model = _select_model(cursor)
            if not model:
                console.print("[red]No model selected.[/red]")
                raise typer.Exit(1)

        # Parse input and output table specifications
        input_parts = input_table.split('.')
        output_parts = output_table.split('.')

        if len(input_parts) < 2:
            console.print(
                "[red]Error: Input must be in format Table.Column "
                "or Database.Table.Column[/red]"
            )
            raise typer.Exit(1)

        if len(output_parts) < 2:
            console.print(
                "[red]Error: Output must be in format Table.Column "
                "or Database.Table.Column[/red]"
            )
            raise typer.Exit(1)

        # Construct full table paths
        if len(input_parts) == 2:
            input_full = f"{db_config['database']}.{input_table}"
        else:
            input_full = input_table

        if len(output_parts) == 2:
            output_full = f"{db_config['database']}.{output_table}"
        else:
            output_full = output_table

        console.print("\n[bold]Batch Generation Configuration:[/bold]")
        console.print(f"[dim]Input: {input_full}[/dim]")
        console.print(f"[dim]Output: {output_full}[/dim]")
        console.print(f"[dim]Model: {model}[/dim]")
        console.print(f"[dim]Language: {language}[/dim]")

        # Build the ML_GENERATE_TABLE call
        options = json.dumps({
            "task": "generation",
            "model_id": model,
            "language": language
        })

        query = f"CALL sys.ML_GENERATE_TABLE('{input_full}', '{output_full}', '{options}')"

        if show_query:
            console.print("\n[bold]SQL Query:[/bold]")
            sql_syntax = Syntax(query, "sql", theme="monokai")
            console.print(Panel(sql_syntax))

        # Execute batch generation
        console.print("\n[bold]Running batch generation...[/bold]")
        cursor.execute(query)
        connection.commit()

        console.print("[green]✓ Batch generation completed![/green]")

        # Show sample results
        output_db, output_tbl = output_full.rsplit('.', 2)[:2]
        cursor.execute(f"SELECT COUNT(*) FROM {output_db}.{output_tbl}")
        count = cursor.fetchone()[0]

        console.print(f"\n[dim]Generated {count} responses[/dim]")

        if Confirm.ask("Show sample results?", default=True):
            cursor.execute(f"SELECT * FROM {output_db}.{output_tbl} LIMIT 3")
            results = cursor.fetchall()

            if results:
                # Get column names
                cursor.execute(f"SHOW COLUMNS FROM {output_db}.{output_tbl}")
                columns = [col[0] for col in cursor.fetchall()]

                # Display results
                for i, row in enumerate(results, 1):
                    console.print(f"\n[bold]Result {i}:[/bold]")
                    for col_name, value in zip(columns, row, strict=False):
                        if isinstance(value, str) and value.startswith('{'):
                            try:
                                parsed = json.loads(value)
                                if 'text' in parsed:
                                    console.print(f"[cyan]{col_name}:[/cyan]")
                                    text = parsed['text']
                                    if len(text) > 200:
                                        console.print(f"  {text[:200]}...")
                                    else:
                                        console.print(f"  {text}")
                            except Exception:
                                val_str = str(value)
                                if len(val_str) > 100:
                                    console.print(f"[cyan]{col_name}:[/cyan] {val_str[:100]}...")
                                else:
                                    console.print(f"[cyan]{col_name}:[/cyan] {value}")
                        else:
                            console.print(f"[cyan]{col_name}:[/cyan] {value}")

        cursor.close()
        connection.close()

    except Error as e:
        console.print(f"[red]✗ Database error: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("models")
def list_models():
    """List available LLMs for text generation."""
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

        # Get available models
        cursor.execute(
            "SELECT model_name, model_type FROM sys.ML_SUPPORTED_LLMS "
            "WHERE model_type = 'generation' "
            "ORDER BY model_name"
        )
        models = cursor.fetchall()

        if not models:
            console.print("[yellow]No generation models found.[/yellow]")
            return

        # Check which models are loaded
        loaded_models = set()
        try:
            cursor.execute("SELECT model_handle FROM sys.ML_MODEL_LOADED")
            loaded_models = {row[0] for row in cursor.fetchall()}
        except Exception:
            # ML_MODEL_LOADED table might not exist in some HeatWave versions
            pass

        # Create table
        table = Table(title="Available Generation Models", show_header=True)
        table.add_column("Model ID", style="cyan")
        table.add_column("Provider", style="green")
        if loaded_models:  # Only show status column if we could get loaded models
            table.add_column("Status", style="yellow")

        for model_name, _ in models:
            if 'cohere.' in model_name or 'meta.' in model_name:
                provider = "OCI Generative AI"
            else:
                provider = "HeatWave In-Database"

            if loaded_models:
                status = "Loaded" if model_name in loaded_models else "Not Loaded"
                table.add_row(model_name, provider, status)
            else:
                table.add_row(model_name, provider)

        console.print(table)
        console.print(f"\n[dim]Total models: {len(models)}[/dim]")

        cursor.close()
        connection.close()

    except Error as e:
        console.print(f"[red]✗ Database error: {e}[/red]")
        raise typer.Exit(1) from None


def _select_model(cursor) -> str:
    """Let user select a model from available generation models."""
    console.print("\n[bold]Available Generation Models:[/bold]")

    try:
        # Get available models
        cursor.execute(
            "SELECT model_name FROM sys.ML_SUPPORTED_LLMS "
            "WHERE model_type = 'generation' "
            "ORDER BY model_name"
        )
        models = [row[0] for row in cursor.fetchall()]

        if not models:
            console.print("[red]No generation models available.[/red]")
            return None

        # Check which models are loaded
        loaded_models = set()
        try:
            cursor.execute("SELECT model_handle FROM sys.ML_MODEL_LOADED")
            loaded_models = {row[0] for row in cursor.fetchall()}
        except Exception:
            # ML_MODEL_LOADED table might not exist in some HeatWave versions
            pass

        # Group models by provider
        heatwave_models = []
        oci_models = []

        for model in models:
            if 'cohere.' in model or 'meta.' in model:
                oci_models.append(model)
            else:
                heatwave_models.append(model)

        # Display models
        all_models = []

        if heatwave_models:
            console.print("\n[yellow]HeatWave In-Database Models:[/yellow]")
            for i, model in enumerate(heatwave_models, 1):
                if loaded_models:  # Only show status if we could get loaded models
                    if model in loaded_models:
                        status = " [green](Loaded)[/green]"
                    else:
                        status = " [red](Not Loaded)[/red]"
                    console.print(f"{i}. [cyan]{model}[/cyan]{status}")
                else:
                    console.print(f"{i}. [cyan]{model}[/cyan]")
                all_models.append(model)

        if oci_models:
            console.print("\n[yellow]OCI Generative AI Models:[/yellow]")
            start_idx = len(heatwave_models) + 1
            for i, model in enumerate(oci_models, start_idx):
                if loaded_models:  # Only show status if we could get loaded models
                    if model in loaded_models:
                        status = " [green](Loaded)[/green]"
                    else:
                        status = " [red](Not Loaded)[/red]"
                    console.print(f"{i}. [cyan]{model}[/cyan]{status}")
                else:
                    console.print(f"{i}. [cyan]{model}[/cyan]")
                all_models.append(model)

        # Get user selection
        while True:
            choice = Prompt.ask(
                "\nSelect model number",
                default="1" if all_models else None,
            )
            try:
                index = int(choice) - 1
                if 0 <= index < len(all_models):
                    selected_model = all_models[index]
                    if loaded_models and selected_model not in loaded_models:
                        console.print(
                            f"\n[yellow]Warning: Model '{selected_model}' is not loaded.[/yellow]"
                        )
                        console.print(
                            "[yellow]You may need to load it first or "
                            "it may not be available in your account.[/yellow]"
                        )
                        if not Confirm.ask("Continue anyway?", default=False):
                            continue
                    return selected_model
                else:
                    console.print("[red]Invalid selection. Please try again.[/red]")
            except ValueError:
                console.print("[red]Please enter a number.[/red]")

    except Exception as e:
        console.print(f"[red]Error listing models: {str(e)}[/red]")
        return None


def _generate_text(cursor, query: str, model: str, language: str, show_query: bool):
    """Execute text generation query and display results."""
    try:
        # Set the query variable
        cursor.execute("SET @query = %s", (query,))

        # Build the ML_GENERATE call
        options = json.dumps({
            "task": "generation",
            "model_id": model,
            "language": language
        })

        sql_query = f"SELECT sys.ML_GENERATE(@query, '{options}')"

        if show_query:
            console.print("\n[bold]SQL Query:[/bold]")
            sql_syntax = Syntax(sql_query, "sql", theme="monokai")
            console.print(Panel(sql_syntax))

        # Execute generation
        console.print("\n[dim]Generating...[/dim]")
        cursor.execute(sql_query)
        result = cursor.fetchone()[0]

        # Parse and display result
        if result:
            try:
                parsed = json.loads(result)
                if 'text' in parsed:
                    console.print("\n[bold green]Generated Text:[/bold green]")
                    console.print(Panel(parsed['text'], border_style="green"))
                else:
                    console.print(f"\n[yellow]Result: {result}[/yellow]")
            except Exception:
                console.print(f"\n[yellow]Result: {result}[/yellow]")
        else:
            console.print("[red]No result generated.[/red]")

    except Error as e:
        console.print(f"[red]✗ Generation failed: {e}[/red]")
