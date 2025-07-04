
import typer

from heatwaved.commands import config, genai, generate, init, lakehouse, schema, test

app = typer.Typer(
    name="heatwaved",
    help="A CLI tool for Oracle MySQL HeatWave POC demonstrations",
    no_args_is_help=True,
)

app.add_typer(init.app, name="init", help="Initialize HeatWave configuration")
app.add_typer(test.app, name="test", help="Test HeatWave and OCI connections")
app.add_typer(config.app, name="config", help="Manage HeatWave configuration")
app.add_typer(schema.app, name="schema", help="Manage database schemas")
app.add_typer(genai.app, name="genai", help="Manage HeatWave GenAI features")
app.add_typer(lakehouse.app, name="lakehouse", help="Configure HeatWave Lakehouse access")
app.add_typer(generate.app, name="generate", help="Generate text content using HeatWave GenAI")

if __name__ == "__main__":
    app()
